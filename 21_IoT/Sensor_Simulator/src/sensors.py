"""Sensor simulator: seeded virtual sensors with CSV logging - offline.

Simulates a small fleet of temperature, humidity, and motion sensors with
numpy's seeded RNG, applies configurable fault injection (spike, drift,
stuck, dropout), logs readings to CSV, and reloads/summarises those logs.
Everything is generated locally - no real devices, no network, no API keys.
"""

from __future__ import annotations

import json
import logging
import tempfile
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

LOG = logging.getLogger("sensors")

SENSOR_KINDS = ("temperature", "humidity", "motion")
FAULT_TYPES = ("none", "spike", "drift", "stuck", "dropout")
FAULT_KINDS = ("spike", "drift", "stuck", "dropout")
REQUIRED_COLUMNS = ("timestamp", "sensor", "kind", "value", "fault")
SUMMARY_COLUMNS = ("sensor", "kind", "readings", "min", "max", "mean", "faults")

DEFAULT_TICKS = 48
DEFAULT_INTERVAL_S = 5.0
DEFAULT_SEED = 42
DEFAULT_START = 1772323200  # 2026-03-01T00:00:00Z

# How much each fault kind shifts a reading per application.
FAULT_DELTA = {"temperature": 15.0, "humidity": 30.0, "motion": 1.0}
FAULT_DRIFT = {"temperature": 1.5, "humidity": 4.0, "motion": 1.0}


class SensorError(RuntimeError):
    """Raised for invalid configurations, bad logs, and simulation failures."""


# --------------------------------------------------------------------------- #
# Timestamps
# --------------------------------------------------------------------------- #
def format_ts(epoch: float) -> str:
    """Epoch seconds -> ISO-8601 UTC string ending in Z."""
    moment = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(text: str) -> float:
    """ISO-8601 timestamp (Z or offset) -> epoch seconds."""
    raw = str(text).strip()
    if raw.endswith("Z") or raw.endswith("z"):
        raw = raw[:-1]
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise SensorError(f"invalid timestamp: {text!r}") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


# --------------------------------------------------------------------------- #
# Fleet and fault configuration
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SensorSpec:
    """Static description of one virtual sensor."""

    name: str
    kind: str
    base: float = 0.0
    amplitude: float = 0.0
    noise_std: float = 0.0
    period_ticks: float = 96.0
    phase: float = 0.0
    probability: float = 0.1


@dataclass(frozen=True)
class FaultSpec:
    """Injected fault window: sensor:kind:start:end (ticks inclusive)."""

    sensor: str
    kind: str
    start: int
    end: int

    def validate(self) -> None:
        if not str(self.sensor).strip():
            raise SensorError("fault sensor name must be non-empty")
        if self.kind not in FAULT_KINDS:
            raise SensorError(
                f"unknown fault kind: {self.kind!r} "
                f"(choose from {', '.join(FAULT_KINDS)})")
        if self.start < 0:
            raise SensorError(f"fault start must be >= 0, got {self.start}")
        if self.end < self.start:
            raise SensorError(
                f"fault window end {self.end} is before start {self.start}")


DEFAULT_FLEET = (
    SensorSpec("living_room_temp", "temperature",
               base=22.0, amplitude=3.0, noise_std=0.35, period_ticks=96.0),
    SensorSpec("living_room_humidity", "humidity",
               base=55.0, amplitude=6.0, noise_std=1.2,
               period_ticks=96.0, phase=1.6),
    SensorSpec("hallway_motion", "motion",
               probability=0.15),
)


def default_fleet(kind: str | None = None) -> tuple[SensorSpec, ...]:
    """The bundled fleet, optionally filtered to one sensor kind."""
    if kind is None:
        return DEFAULT_FLEET
    if kind not in SENSOR_KINDS:
        raise SensorError(
            f"unknown sensor kind: {kind!r} "
            f"(choose from {', '.join(SENSOR_KINDS)})")
    return tuple(spec for spec in DEFAULT_FLEET if spec.kind == kind)


def parse_fault(text: str) -> FaultSpec:
    """Parse 'SENSOR:KIND:START:END' into a validated FaultSpec."""
    parts = [part.strip() for part in str(text).split(":")]
    if len(parts) != 4:
        raise SensorError(
            f"fault must be SENSOR:KIND:START:END, got {text!r}")
    sensor, kind, start_text, end_text = parts
    try:
        start = int(start_text)
        end = int(end_text)
    except ValueError as exc:
        raise SensorError(f"fault ticks must be integers, got {text!r}") from exc
    fault = FaultSpec(sensor=sensor, kind=kind, start=start, end=end)
    fault.validate()
    return fault


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #
def _rng_for(seed: int, name: str) -> np.random.Generator:
    """Stable per-sensor RNG (crc32 of the name, independent of ordering)."""
    return np.random.default_rng([int(seed), zlib.crc32(name.encode("utf-8"))])


def _sample(spec: SensorSpec, rng: np.random.Generator, tick: int) -> float:
    """One noise draw for a sensor at the given tick."""
    if spec.kind == "motion":
        return 1.0 if rng.random() < spec.probability else 0.0
    angle = 2.0 * np.pi * tick / spec.period_ticks + spec.phase
    value = (spec.base + spec.amplitude * np.sin(angle)
             + rng.normal(0.0, spec.noise_std))
    return float(value)


def _apply_delta(kind: str, value: float, delta: float) -> float:
    """Apply a fault shift; motion stays binary (0/1)."""
    if kind == "motion":
        return 1.0 if value + delta >= 0.5 else 0.0
    return value + delta


def _active_fault(faults: tuple[FaultSpec, ...], sensor: str,
                  tick: int) -> FaultSpec | None:
    for fault in faults:
        if fault.sensor == sensor and fault.start <= tick <= fault.end:
            return fault
    return None


def simulate(specs: tuple[SensorSpec, ...] = DEFAULT_FLEET,
             ticks: int = DEFAULT_TICKS,
             interval_s: float = DEFAULT_INTERVAL_S,
             start_epoch: int = DEFAULT_START,
             seed: int = DEFAULT_SEED,
             faults: tuple[FaultSpec, ...] = ()) -> pd.DataFrame:
    """Generate a deterministic reading log for a fleet of sensors."""
    # general checks first, specific checks later (first error wins)
    if ticks < 1:
        raise SensorError(f"ticks must be >= 1, got {ticks}")
    if not np.isfinite(interval_s) or interval_s <= 0:
        raise SensorError(f"interval must be > 0, got {interval_s}")
    if not isinstance(seed, (int, np.integer)) or seed < 0:
        raise SensorError(f"seed must be a non-negative integer, got {seed}")

    specs = tuple(specs)
    if not specs:
        raise SensorError("need at least one sensor")
    for spec in specs:
        if not str(spec.name).strip():
            raise SensorError("sensor name must be non-empty")
        if spec.kind not in SENSOR_KINDS:
            raise SensorError(
                f"unknown sensor kind: {spec.kind!r} "
                f"(choose from {', '.join(SENSOR_KINDS)})")
        if not np.isfinite(spec.period_ticks) or spec.period_ticks <= 0:
            raise SensorError(
                f"period_ticks must be > 0 for {spec.name!r}, "
                f"got {spec.period_ticks}")

    faults = tuple(faults)
    for fault in faults:
        fault.validate()
    names = [spec.name for spec in specs]
    if len(set(names)) != len(names):
        duplicates = sorted({n for n in names if names.count(n) > 1})
        raise SensorError(f"duplicate sensor name(s): "
                          f"{', '.join(duplicates)}")
    known = set(names)
    for fault in faults:
        if fault.sensor not in known:
            raise SensorError(
                f"fault targets unknown sensor: {fault.sensor!r} "
                f"(known: {', '.join(sorted(known))})")
        if fault.end >= ticks:
            raise SensorError(
                f"fault window {fault.start}..{fault.end} exceeds ticks "
                f"0..{ticks - 1}")
    for i, first in enumerate(faults):
        for second in faults[i + 1:]:
            if (first.sensor == second.sensor
                    and not (first.end < second.start
                             or second.end < first.start)):
                raise SensorError(
                    f"overlapping faults for sensor {first.sensor!r}: "
                    f"{first.start}..{first.end} and "
                    f"{second.start}..{second.end}")

    # tick-major order keeps the whole log timestamp-monotonic
    rngs = {spec.name: _rng_for(seed, spec.name) for spec in specs}
    stuck: dict[str, float | None] = {spec.name: None for spec in specs}
    rows: list[dict[str, object]] = []
    for tick in range(ticks):
        epoch = start_epoch + tick * interval_s
        for spec in specs:
            fault = _active_fault(faults, spec.name, tick)
            if fault is not None and fault.kind == "dropout":
                stuck[spec.name] = None
                continue  # reading is lost entirely
            value = _sample(spec, rngs[spec.name], tick)
            if fault is not None:
                if fault.kind == "stuck":
                    if stuck[spec.name] is None:
                        stuck[spec.name] = value
                    value = stuck[spec.name]
                elif fault.kind == "spike":
                    value = _apply_delta(spec.kind, value,
                                         FAULT_DELTA[spec.kind])
                elif fault.kind == "drift":
                    elapsed = tick - fault.start + 1
                    value = _apply_delta(spec.kind, value,
                                         FAULT_DRIFT[spec.kind] * elapsed)
            else:
                stuck[spec.name] = None
            if spec.kind == "humidity":
                value = float(np.clip(value, 0.0, 100.0))
            rows.append({
                "timestamp": format_ts(epoch),
                "sensor": spec.name,
                "kind": spec.kind,
                # 6 decimals: stays exact through pandas' CSV float format
                "value": float(round(value, 6)),
                "fault": fault.kind if fault is not None else "none",
            })

    frame = pd.DataFrame(rows, columns=list(REQUIRED_COLUMNS))
    LOG.info("simulated %d readings for %d sensors", len(frame), len(specs))
    return frame


# --------------------------------------------------------------------------- #
# CSV logging
# --------------------------------------------------------------------------- #
def log_readings(frame: pd.DataFrame, path: str | Path) -> Path:
    """Write a reading log to CSV (creates parent directories)."""
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise SensorError(f"cannot log: missing column(s): "
                          f"{', '.join(missing)}")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    try:
        out["value"] = pd.to_numeric(out["value"], errors="raise")
    except (TypeError, ValueError) as exc:
        raise SensorError(f"cannot log: 'value' must be numeric: {exc}") from exc
    out.to_csv(target, index=False)
    return target


def load_log(path: str | Path) -> pd.DataFrame:
    """Load and validate a reading log CSV."""
    source = Path(path)
    if not source.is_file():
        raise SensorError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise SensorError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise SensorError(f"missing column(s): {', '.join(missing)} "
                          f"(expected {', '.join(REQUIRED_COLUMNS)})")
    if frame.empty:
        raise SensorError(f"no rows in {source.name}")

    frame = frame.copy()
    # empty CSV cells -> NaN -> fillna before astype(str)
    for column in ("timestamp", "sensor", "kind", "fault"):
        frame[column] = frame[column].fillna("").astype(str)
    if (frame["sensor"].str.strip() == "").any():
        raise SensorError("column 'sensor' contains empty values")
    unknown_kinds = sorted(set(frame["kind"]) - set(SENSOR_KINDS))
    if unknown_kinds:
        raise SensorError("column 'kind' has unknown sensor kind(s): "
                          f"{', '.join(unknown_kinds)}")
    unknown_faults = sorted(set(frame["fault"]) - set(FAULT_TYPES))
    if unknown_faults:
        raise SensorError("column 'fault' has unknown fault label(s): "
                          f"{', '.join(unknown_faults)}")

    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    if frame["value"].isna().any():
        count = int(frame["value"].isna().sum())
        raise SensorError(f"column 'value' contains {count} missing or "
                          f"non-numeric values")
    if not np.isfinite(frame["value"]).all():
        raise SensorError("column 'value' must be finite")

    try:
        epochs = np.asarray([parse_ts(text) for text in frame["timestamp"]],
                            dtype=float)
    except SensorError as exc:
        raise SensorError(f"column 'timestamp': {exc}") from exc
    if np.any(np.diff(epochs) < 0):
        raise SensorError("column 'timestamp' must be non-decreasing")

    motion = frame[frame["kind"] == "motion"]
    if not motion.empty and not motion["value"].isin([0.0, 1.0]).all():
        raise SensorError("column 'value' for motion sensors must be 0 or 1")

    frame = frame.reset_index(drop=True)
    LOG.info("loaded %d readings from %s", len(frame), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Summaries
# --------------------------------------------------------------------------- #
def summarize(frame: pd.DataFrame) -> pd.DataFrame:
    """Per-sensor aggregates: counts, range, mean, injected faults."""
    rows = []
    for sensor, group in frame.groupby("sensor", sort=True):
        values = group["value"]
        rows.append({
            "sensor": sensor,
            "kind": group["kind"].iloc[0],
            "readings": len(group),
            "min": round(float(values.min()), 3),
            "max": round(float(values.max()), 3),
            "mean": round(float(values.mean()), 3),
            "faults": int((group["fault"] != "none").sum()),
        })
    return pd.DataFrame(rows, columns=list(SUMMARY_COLUMNS))


def render_summary(frame: pd.DataFrame) -> str:
    """Fixed-width text table used by the CLI and the demo."""
    table = summarize(frame)
    header = (f"{'sensor':<22} {'kind':<12} {'n':>4} {'min':>8} "
              f"{'max':>8} {'mean':>8} {'faults':>6}")
    lines = ["Sensor summary:", header, "-" * len(header)]
    for _, row in table.iterrows():
        lines.append(f"{row['sensor']:<22} {row['kind']:<12} "
                     f"{row['readings']:>4} {row['min']:>8.3f} "
                     f"{row['max']:>8.3f} {row['mean']:>8.3f} "
                     f"{row['faults']:>6}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "sensor_sample.csv"
DEMO_FAULTS = (
    FaultSpec("living_room_temp", "spike", 30, 33),
    FaultSpec("hallway_motion", "dropout", 10, 12),
)


def run_demo(json_path: Path | None = None) -> int:
    """Simulate the bundled fleet, verify against data/, log + summarise."""
    print("=" * 68)
    print(" SENSOR SIMULATOR - offline demo")
    print(" Seeded virtual sensors; CSV logging; no network, no devices.")
    print("=" * 68)

    if not DEMO_CSV.is_file():
        raise SensorError(f"bundled sample not found: {DEMO_CSV}")

    specs = default_fleet()
    frame = simulate(specs, faults=DEMO_FAULTS)
    bundled = load_log(DEMO_CSV)
    print(f"\nGenerated {len(frame)} readings for {len(specs)} sensors "
          f"({DEFAULT_TICKS} ticks x {DEFAULT_INTERVAL_S:g}s, "
          f"seed {DEFAULT_SEED})")

    # --- cross-checks the demo asserts ----------------------------------- #
    assert len(frame) == len(bundled), "row count differs from bundled sample"
    assert frame.equals(bundled), "readings differ from bundled sample"
    again = simulate(specs, faults=DEMO_FAULTS)
    assert again.equals(frame), "simulation is not deterministic"

    clean = simulate(specs)
    assert len(clean) == len(specs) * DEFAULT_TICKS, "clean run must be full"
    assert len(frame) == len(clean) - 3, "dropout must drop 3 readings"

    temp = frame[frame["sensor"] == "living_room_temp"]
    spiked = temp[temp["fault"] == "spike"]
    assert len(spiked) == 4, "spike window must cover 4 ticks"
    clean_temp = clean[clean["sensor"] == "living_room_temp"]["value"]
    deltas = spiked["value"].to_numpy() - clean_temp.iloc[30:34].to_numpy()
    assert np.allclose(deltas, FAULT_DELTA["temperature"]), \
        "spike must add exactly +15 C"
    assert float(spiked["value"].max()) > 35.0, "spike did not lift temperature"

    motion = frame[frame["kind"] == "motion"]
    assert set(motion["value"]) <= {0.0, 1.0}, "motion must stay binary"
    assert int((frame["fault"] == "dropout").sum()) == 0, \
        "dropout rows must be absent from the log"
    humidity = frame[frame["kind"] == "humidity"]
    assert humidity["value"].between(0, 100).all(), "humidity out of 0..100"

    with tempfile.TemporaryDirectory() as tmp:
        written = log_readings(frame, Path(tmp) / "run_log.csv")
        reloaded = load_log(written)
        assert reloaded.equals(frame), "CSV round-trip lost data"

    summary = summarize(frame)
    assert len(summary) == len(specs), "one summary row per sensor"
    assert int(summary["readings"].sum()) == len(frame), \
        "summary must count every reading"
    assert (summary["readings"] > 0).all(), "sensor with no readings"
    assert int(summary.loc[summary["sensor"] == "living_room_temp",
                           "faults"].iloc[0]) == 4, "spike fault count"
    assert int(summary.loc[summary["sensor"] == "hallway_motion",
                           "faults"].iloc[0]) == 0, \
        "dropouts are absent, not counted"

    print()
    print(render_summary(frame))
    print(f"\nInjected faults: spike on living_room_temp (ticks 30..33, "
          f"+15 C), dropout on hallway_motion (ticks 10..12, readings lost)")
    print(f"CSV round-trip verified in a temp directory "
          f"({len(reloaded)} rows reloaded)")

    if json_path is not None:
        payload = {
            "mode": "demo",
            "seed": DEFAULT_SEED,
            "ticks": DEFAULT_TICKS,
            "readings": len(frame),
            "summary": summary.to_dict("records"),
        }
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {json_path}")

    print("\nCross-checks OK: bundled sample matched exactly, deterministic "
          "re-run, spike +15 C, dropout drops 3 rows, humidity in 0..100, "
          "CSV round-trip, summary totals match")
    print("Demo completed successfully.")
    return 0
