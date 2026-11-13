"""Sensor data analysis: rolling statistics, anomalies, gaps, flatlines.

Loads a bundled multi-sensor CSV, then answers the questions an operator
actually asks of a telemetry export: what is normal, what is an outlier,
where is data missing, where did a sensor freeze, and how do sensors
correlate? Everything runs locally with pandas - no network, no database.

Public API
----------
generate_readings   deterministic bundled telemetry (with known faults)
bundle_readings     write data/readings.csv
load_readings       read + validate a telemetry CSV
add_rolling         per-sensor rolling mean and standard deviation
detect_anomalies    rolling z-score outliers
detect_gaps         missing-sample intervals
detect_flatlines    runs of identical consecutive readings
resample_metric     downsample one series to a coarser rule
sensor_summary      per-sensor descriptive statistics
correlation         Pearson correlation between sensors
render_report       human-readable analysis summary
run_demo            offline demo with self-checks
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
READINGS_FILE = DATA_DIR / "readings.csv"

COLUMNS = ("timestamp", "sensor", "metric", "value")
SENSORS = ("living_room", "bedroom", "bathroom")
METRIC = "temperature"
SAMPLE_SECONDS = 60
SAMPLES = 120
DEFAULT_WINDOW = 15
DEFAULT_Z = 3.0
DEFAULT_GAP_SECONDS = 120
DEFAULT_FLAT_RUN = 5

START = "2026-03-01T00:00:00Z"
# fault injection points, expressed in sample indices
SPIKE_AT = 40
DROP_AT = 70
GAP_AT = 30
GAP_LENGTH = 5
FLAT_AT = 90
FLAT_LENGTH = 7


class AnalysisError(RuntimeError):
    """Raised for invalid data, bad parameters or corrupted bundled files."""


# --------------------------------------------------------------------------- #
# Bundled data
# --------------------------------------------------------------------------- #
def _series(offset: float, amplitude: float, phase: float) -> list[float]:
    values = []
    for index in range(SAMPLES):
        wave = math.sin((index + phase) / 9.0)
        drift = (index / SAMPLES) * 0.6
        jitter = 0.12 * math.sin(index * 2.7 + phase)
        values.append(round(20.0 + offset + amplitude * wave + drift + jitter,
                            3))
    return values


def generate_readings() -> pd.DataFrame:
    """Deterministic 3-sensor temperature log with four injected faults."""
    base = pd.Timestamp(START)
    rows = []
    for sensor, offset, amplitude, phase in zip(SENSORS,
                                                (0.0, 1.4, -0.8),
                                                (1.0, 0.7, 1.3),
                                                (0.0, 3.0, 6.0)):
        values = _series(offset, amplitude, phase)
        for index, value in enumerate(values):
            if sensor == "living_room" and index == SPIKE_AT:
                value += 8.0
            if sensor == "bedroom" and index == DROP_AT:
                value -= 7.0
            if sensor == "living_room" and FLAT_AT <= index < FLAT_AT + FLAT_LENGTH:
                value = values[FLAT_AT]
            if sensor == "bathroom" and GAP_AT <= index < GAP_AT + GAP_LENGTH:
                continue
            stamp = base + pd.to_timedelta(SAMPLE_SECONDS * index, unit="s")
            rows.append({"timestamp": stamp, "sensor": sensor,
                         "metric": METRIC, "value": value})
    frame = pd.DataFrame(rows, columns=list(COLUMNS))
    return frame.sort_values(["timestamp", "sensor"]).reset_index(drop=True)


def bundle_readings(path: Path | str | None = None) -> Path:
    target = Path(path) if path is not None else READINGS_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    generate_readings().to_csv(target, index=False)
    return target


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_readings(path: Path | str | None = None) -> pd.DataFrame:
    target = Path(path) if path is not None else READINGS_FILE
    if not target.is_file():
        raise AnalysisError(f"readings not found: {target}")
    try:
        frame = pd.read_csv(target)
    except Exception as exc:  # pragma: no cover - pandas message varies
        raise AnalysisError(f"could not parse {target.name}: {exc}") from exc
    missing = [column for column in COLUMNS if column not in frame.columns]
    if missing:
        raise AnalysisError(f"missing column(s): {', '.join(missing)}")
    if frame.empty:
        raise AnalysisError(f"no rows in {target.name}")

    frame = frame[list(COLUMNS)].copy()
    for column in ("sensor", "metric"):
        frame[column] = frame[column].fillna("").astype(str).str.strip()
        if (frame[column] == "").any():
            raise AnalysisError(f"column {column!r} contains empty values")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    if frame["value"].isna().any():
        count = int(frame["value"].isna().sum())
        raise AnalysisError(f"column 'value' has {count} non-numeric values")
    if not np.isfinite(frame["value"].to_numpy()).all():
        raise AnalysisError("column 'value' must be finite")

    try:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True,
                                            errors="raise")
    except (ValueError, TypeError) as exc:
        raise AnalysisError(f"column 'timestamp': {exc}") from exc
    return frame.sort_values(["timestamp", "sensor"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Rolling statistics and anomalies
# --------------------------------------------------------------------------- #
def add_rolling(frame: pd.DataFrame, window: int = DEFAULT_WINDOW
                ) -> pd.DataFrame:
    """Attach a per-series rolling mean and standard deviation."""
    if window < 2:
        raise AnalysisError(f"window must be >= 2, got {window}")
    if frame.empty:
        raise AnalysisError("cannot compute rolling stats on no rows")
    result = frame.sort_values(["sensor", "metric", "timestamp"]).copy()
    grouped = result.groupby(["sensor", "metric"], sort=False)["value"]
    minimum = max(2, window // 3)
    result["rolling_mean"] = grouped.transform(
        lambda series: series.rolling(window, min_periods=minimum).mean())
    result["rolling_std"] = grouped.transform(
        lambda series: series.rolling(window, min_periods=minimum).std())
    return result.reset_index(drop=True)


def detect_anomalies(frame: pd.DataFrame, z: float = DEFAULT_Z,
                     window: int = DEFAULT_WINDOW) -> pd.DataFrame:
    """Rows whose value deviates from its rolling mean by more than z sigma."""
    if not math.isfinite(z) or z <= 0:
        raise AnalysisError(f"z must be > 0, got {z}")
    rolled = add_rolling(frame, window=window)
    deviation = (rolled["value"] - rolled["rolling_mean"]).abs()
    threshold = z * rolled["rolling_std"]
    mask = (rolled["rolling_std"] > 0) & (deviation > threshold)
    flagged = rolled.loc[mask].copy()
    flagged["deviation"] = (flagged["value"] - flagged["rolling_mean"]).round(3)
    flagged["z_score"] = (flagged["deviation"] / flagged["rolling_std"]).round(3)
    return flagged[list(COLUMNS) + ["rolling_mean", "deviation", "z_score"]] \
        .reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Gaps and flatlines
# --------------------------------------------------------------------------- #
@dataclass
class Gap:
    sensor: str
    metric: str
    after: pd.Timestamp
    before: pd.Timestamp
    seconds: float
    missing: int

    def to_dict(self) -> dict:
        return {"sensor": self.sensor, "metric": self.metric,
                "after": str(self.after), "before": str(self.before),
                "seconds": self.seconds, "missing": self.missing}


def detect_gaps(frame: pd.DataFrame,
                max_gap_s: float = DEFAULT_GAP_SECONDS) -> list[Gap]:
    if max_gap_s <= 0:
        raise AnalysisError(f"max_gap_s must be > 0, got {max_gap_s}")
    if frame.empty:
        raise AnalysisError("cannot detect gaps in no rows")
    gaps: list[Gap] = []
    ordered = frame.sort_values(["sensor", "metric", "timestamp"])
    for (sensor, metric), group in ordered.groupby(["sensor", "metric"],
                                                   sort=True):
        stamps = group["timestamp"].tolist()
        for previous, current in zip(stamps, stamps[1:]):
            seconds = (current - previous).total_seconds()
            if seconds > max_gap_s:
                gaps.append(Gap(sensor=sensor, metric=metric, after=previous,
                                before=current, seconds=seconds,
                                missing=int(round(seconds / SAMPLE_SECONDS)) - 1))
    return gaps


def detect_flatlines(frame: pd.DataFrame,
                     min_run: int = DEFAULT_FLAT_RUN) -> list[dict]:
    if min_run < 2:
        raise AnalysisError(f"min_run must be >= 2, got {min_run}")
    if frame.empty:
        raise AnalysisError("cannot detect flatlines in no rows")
    runs: list[dict] = []
    ordered = frame.sort_values(["sensor", "metric", "timestamp"])
    for (sensor, metric), group in ordered.groupby(["sensor", "metric"],
                                                   sort=True):
        values = group["value"].tolist()
        stamps = group["timestamp"].tolist()
        start = 0
        for index in range(1, len(values) + 1):
            finished = index == len(values) or values[index] != values[start]
            if finished and index - start >= min_run:
                runs.append({
                    "sensor": sensor, "metric": metric,
                    "value": values[start], "length": index - start,
                    "start": stamps[start], "end": stamps[index - 1],
                })
            if finished:
                start = index
    return runs


# --------------------------------------------------------------------------- #
# Resampling, summaries, correlation
# --------------------------------------------------------------------------- #
def resample_metric(frame: pd.DataFrame, sensor: str, metric: str,
                    rule: str = "10min") -> pd.DataFrame:
    if not rule:
        raise AnalysisError("rule must be a non-empty pandas offset")
    subset = frame[(frame["sensor"] == sensor) & (frame["metric"] == metric)]
    if subset.empty:
        raise AnalysisError(f"no rows for {sensor}/{metric}")
    series = (subset.set_index("timestamp")["value"]
              .sort_index().resample(rule).agg(["mean", "count"]))
    series = series[series["count"] > 0]
    return series.round(3)


def sensor_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise AnalysisError("cannot summarise no rows")
    summary = (frame.groupby(["sensor", "metric"])["value"]
               .agg(["count", "mean", "std", "min", "max"])
               .round(3))
    return summary.reset_index()


def correlation(frame: pd.DataFrame, metric: str = METRIC) -> pd.DataFrame:
    subset = frame[frame["metric"] == metric]
    if subset.empty:
        raise AnalysisError(f"no rows for metric {metric!r}")
    pivot = subset.pivot_table(index="timestamp", columns="sensor",
                               values="value")
    if pivot.shape[1] < 2:
        raise AnalysisError("need at least two sensors to correlate")
    return pivot.corr().round(4)


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def render_report(frame: pd.DataFrame, anomalies: pd.DataFrame,
                  gaps: list[Gap], flatlines: list[dict]) -> str:
    summary = sensor_summary(frame)
    lines = [
        "SENSOR DATA ANALYZER",
        "=" * 78,
        f"Rows: {len(frame)}    Sensors: {frame['sensor'].nunique()}    "
        f"Anomalies: {len(anomalies)}    Gaps: {len(gaps)}    "
        f"Flatlines: {len(flatlines)}",
        "",
        f"{'sensor':<14} {'count':>6} {'mean':>8} {'std':>7} {'min':>8} "
        f"{'max':>8}",
        "-" * 78,
    ]
    for row in summary.itertuples(index=False):
        lines.append(f"{row.sensor:<14} {row.count:>6} {row.mean:>8.2f} "
                     f"{row.std:>7.2f} {row.min:>8.2f} {row.max:>8.2f}")
    if len(anomalies):
        lines += ["", "Anomalies:"]
        for row in anomalies.itertuples(index=False):
            lines.append(f"  {row.timestamp}  {row.sensor:<12} "
                         f"value {row.value:.2f}  z {row.z_score:+.2f}")
    if gaps:
        lines += ["", "Gaps:"]
        for gap in gaps:
            lines.append(f"  {gap.sensor:<12} {gap.after} -> {gap.before} "
                         f"({gap.missing} missing samples)")
    if flatlines:
        lines += ["", "Flatlines:"]
        for run in flatlines:
            lines.append(f"  {run['sensor']:<12} {run['length']} x "
                         f"{run['value']:.2f} from {run['start']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(data_dir: Path | None = None) -> int:
    root = data_dir or DATA_DIR
    print("=" * 78)
    print(" SENSOR DATA ANALYZER - offline demo")
    print(" Rolling z-scores, gap detection, flatlines, resampling.")
    print("=" * 78)

    expected = generate_readings()
    frame = load_readings(root / "readings.csv")
    if len(frame) != len(expected):
        raise AnalysisError("bundled readings do not match the generator")
    if not frame["value"].round(3).equals(expected["value"].round(3)):
        raise AnalysisError("bundled readings differ from the generator")
    print(f"\nLoaded          : {len(frame)} rows, "
          f"{frame['sensor'].nunique()} sensors, "
          f"{frame['timestamp'].min()} .. {frame['timestamp'].max()}")
    assert frame["sensor"].nunique() == len(SENSORS)
    assert abs(len(frame) - (len(SENSORS) * SAMPLES - GAP_LENGTH)) < 1e-9

    summary = sensor_summary(frame)
    assert len(summary) == len(SENSORS)
    assert (summary["count"] > 100).all()
    print("Summary         : " + ", ".join(
        f"{row.sensor} n={row.count}" for row in summary.itertuples()))

    anomalies = detect_anomalies(frame, z=DEFAULT_Z)
    assert len(anomalies) >= 2, "injected spike/drop were not detected"
    flagged = {(str(row.sensor), str(row.timestamp))
               for row in anomalies.itertuples()}
    spike_stamp = pd.Timestamp(START) + pd.to_timedelta(
        SAMPLE_SECONDS * SPIKE_AT, unit="s")
    drop_stamp = pd.Timestamp(START) + pd.to_timedelta(
        SAMPLE_SECONDS * DROP_AT, unit="s")
    assert ("living_room", str(spike_stamp)) in flagged, flagged
    assert ("bedroom", str(drop_stamp)) in flagged, flagged
    print(f"Anomalies       : {len(anomalies)} flagged by a "
          f"{DEFAULT_Z:g}-sigma rolling test")

    gaps = detect_gaps(frame)
    assert len(gaps) == 1, [gap.to_dict() for gap in gaps]
    assert gaps[0].sensor == "bathroom"
    assert gaps[0].missing == GAP_LENGTH
    print(f"Gaps            : {gaps[0].sensor} missing "
          f"{gaps[0].missing} samples after {gaps[0].after}")

    flatlines = detect_flatlines(frame)
    assert flatlines, "the frozen sensor was not detected"
    longest = max(flatlines, key=lambda run: run["length"])
    assert longest["sensor"] == "living_room"
    assert longest["length"] == FLAT_LENGTH
    print(f"Flatlines       : {longest['sensor']} repeated "
          f"{longest['length']} readings ({longest['value']:.2f})")

    coarse = resample_metric(frame, "living_room", METRIC, rule="10min")
    assert len(coarse) == SAMPLES // 10
    assert coarse["count"].sum() == \
        len(frame[frame["sensor"] == "living_room"])
    print(f"Resampled       : living_room 10-min bins -> {len(coarse)} rows")

    corr = correlation(frame)
    assert corr.shape == (len(SENSORS), len(SENSORS))
    assert np.allclose(np.diag(corr.to_numpy()), 1.0)
    assert np.allclose(corr.to_numpy(), corr.to_numpy().T)
    print("Correlation     : " + ", ".join(
        f"{left}-{right} {corr.loc[left, right]:+.2f}"
        for left, right in (("living_room", "bedroom"),
                            ("living_room", "bathroom"))))

    # determinism of the whole analysis
    assert detect_anomalies(frame).equals(anomalies)
    assert [gap.to_dict() for gap in detect_gaps(frame)] == \
        [gap.to_dict() for gap in gaps]

    print()
    print(render_report(frame, anomalies, gaps, flatlines))

    print("\nCross-checks OK: bundled data matches the generator, the "
          "injected spike and drop are flagged, the 5-sample gap and "
          "7-sample flatline are found, resampling conserves rows, "
          "correlation is symmetric")
    print("\nDemo completed successfully.")
    return 0
