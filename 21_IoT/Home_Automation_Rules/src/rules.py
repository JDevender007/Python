"""Home automation rules: an if-then engine over sensor events - offline.

Loads a JSON rule set (threshold conditions with hysteresis and
minimum-duration delays), replays a bundled sensor-event CSV through the
engine, and emits an actuator event log (trigger/release). Everything is
simulated in-process - no hub, no network, no real appliances.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

OPS = (">", ">=", "<", "<=")
EVENT_LABELS = ("trigger", "release")
REQUIRED_RULE_FIELDS = ("id", "sensor", "metric", "condition", "action")
RULE_FIELDS = frozenset(REQUIRED_RULE_FIELDS
                        + ("hysteresis", "min_duration_s", "release"))
CONDITION_FIELDS = frozenset(("op", "threshold"))
ACTION_FIELDS = frozenset(("actuator", "command"))
RELEASE_FIELDS = frozenset(("command",))
EVENT_COLUMNS = ("timestamp", "sensor", "metric", "value")
ACTUATOR_COLUMNS = ("timestamp", "rule", "event", "actuator", "command")


class RuleError(RuntimeError):
    """Raised for invalid rules, bad event logs, and engine failures."""


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
        raise RuleError(f"invalid timestamp: {text!r}") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


# --------------------------------------------------------------------------- #
# Rule model and validation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Rule:
    """One if-then rule: condition on a sensor metric -> actuator command."""

    id: str
    sensor: str
    metric: str
    op: str
    threshold: float
    hysteresis: float = 0.0
    min_duration_s: float = 0.0
    actuator: str = ""
    command: str = ""
    release_command: str | None = None

    def condition(self, value: float) -> bool:
        """Does the raw reading satisfy the trigger condition?"""
        if self.op == ">":
            return value > self.threshold
        if self.op == ">=":
            return value >= self.threshold
        if self.op == "<":
            return value < self.threshold
        return value <= self.threshold

    def released(self, value: float) -> bool:
        """Has an active rule crossed back past threshold +/- hysteresis?"""
        if self.op == ">":
            return value <= self.threshold - self.hysteresis
        if self.op == ">=":
            return value < self.threshold - self.hysteresis
        if self.op == "<":
            return value >= self.threshold + self.hysteresis
        return value > self.threshold + self.hysteresis


def _check_str(value: object, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuleError(message)
    return value


def _check_number(value: object, message: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuleError(message)
    number = float(value)
    if not math.isfinite(number):
        raise RuleError(message)
    return number


def _parse_rule(item: object, index: int, seen: set[str]) -> Rule:
    if not isinstance(item, dict):
        raise RuleError(f"rule {index} must be an object")
    missing = [field for field in REQUIRED_RULE_FIELDS if field not in item]
    if missing:
        raise RuleError(f"rule {index} missing field {missing[0]!r}")
    unknown = sorted(set(item) - RULE_FIELDS)
    if unknown:
        raise RuleError(f"rule {index} has unknown field(s): "
                        f"{', '.join(unknown)}")

    rule_id = _check_str(item["id"], f"rule {index} id must be a "
                                     f"non-empty string")
    if rule_id in seen:
        raise RuleError(f"duplicate rule id: {rule_id!r}")
    seen.add(rule_id)
    sensor = _check_str(item["sensor"],
                        f"rule {rule_id!r} sensor must be a non-empty string")
    metric = _check_str(item["metric"],
                        f"rule {rule_id!r} metric must be a non-empty string")

    condition = item["condition"]
    if not isinstance(condition, dict):
        raise RuleError(f"rule {rule_id!r} condition must be an object")
    unknown = sorted(set(condition) - CONDITION_FIELDS)
    if unknown:
        raise RuleError(f"rule {rule_id!r} condition has unknown field(s): "
                        f"{', '.join(unknown)}")
    if "op" not in condition:
        raise RuleError(f"rule {rule_id!r} condition missing field 'op'")
    if condition["op"] not in OPS:
        raise RuleError(f"rule {rule_id!r} has invalid op: "
                        f"{condition['op']!r} (choose from {', '.join(OPS)})")
    if "threshold" not in condition:
        raise RuleError(f"rule {rule_id!r} condition missing field "
                        f"'threshold'")
    threshold = _check_number(
        condition["threshold"],
        f"rule {rule_id!r} threshold must be a finite number")

    hysteresis = 0.0
    if "hysteresis" in item:
        hysteresis = _check_number(
            item["hysteresis"],
            f"rule {rule_id!r} hysteresis must be a finite number")
        if hysteresis < 0:
            raise RuleError(f"rule {rule_id!r} hysteresis must be >= 0, "
                            f"got {hysteresis:g}")
    min_duration = 0.0
    if "min_duration_s" in item:
        min_duration = _check_number(
            item["min_duration_s"],
            f"rule {rule_id!r} min_duration_s must be a finite number")
        if min_duration < 0:
            raise RuleError(f"rule {rule_id!r} min_duration_s must be >= 0, "
                            f"got {min_duration:g}")

    action = item["action"]
    if not isinstance(action, dict):
        raise RuleError(f"rule {rule_id!r} action must be an object")
    unknown = sorted(set(action) - ACTION_FIELDS)
    if unknown:
        raise RuleError(f"rule {rule_id!r} action has unknown field(s): "
                        f"{', '.join(unknown)}")
    actuator = _check_str(action.get("actuator"),
                          f"rule {rule_id!r} action.actuator must be a "
                          f"non-empty string")
    command = _check_str(action.get("command"),
                         f"rule {rule_id!r} action.command must be a "
                         f"non-empty string")

    release_command: str | None = None
    if "release" in item:
        release = item["release"]
        if not isinstance(release, dict):
            raise RuleError(f"rule {rule_id!r} release must be an object")
        unknown = sorted(set(release) - RELEASE_FIELDS)
        if unknown:
            raise RuleError(f"rule {rule_id!r} release has unknown "
                            f"field(s): {', '.join(unknown)}")
        release_command = _check_str(
            release.get("command"),
            f"rule {rule_id!r} release.command must be a non-empty string")

    return Rule(id=rule_id, sensor=sensor, metric=metric,
                op=condition["op"], threshold=threshold,
                hysteresis=hysteresis, min_duration_s=min_duration,
                actuator=actuator, command=command,
                release_command=release_command)


def parse_rules(data: object) -> list[Rule]:
    """Validate a decoded rules document into Rule objects."""
    if not isinstance(data, dict):
        raise RuleError("rules file must be a JSON object")
    if "rules" not in data:
        raise RuleError("missing top-level 'rules' list")
    raw = data["rules"]
    if not isinstance(raw, list):
        raise RuleError("'rules' must be a list")
    if not raw:
        raise RuleError("rules list is empty")
    seen: set[str] = set()
    return [_parse_rule(item, index, seen)
            for index, item in enumerate(raw)]


def load_rules(path: str | Path) -> list[Rule]:
    """Load and validate a JSON rules file."""
    source = Path(path)
    if not source.is_file():
        raise RuleError(f"file not found: {source}")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuleError(f"invalid JSON in {source.name}: {exc}") from exc
    return parse_rules(data)


# --------------------------------------------------------------------------- #
# Event logs
# --------------------------------------------------------------------------- #
def load_events(path: str | Path) -> pd.DataFrame:
    """Load and validate a sensor-event CSV (timestamp,sensor,metric,value)."""
    source = Path(path)
    if not source.is_file():
        raise RuleError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise RuleError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in EVENT_COLUMNS if c not in frame.columns]
    if missing:
        raise RuleError(f"missing column(s): {', '.join(missing)} "
                        f"(expected {', '.join(EVENT_COLUMNS)})")
    if frame.empty:
        raise RuleError(f"no rows in {source.name}")

    frame = frame.copy()
    # empty CSV cells -> NaN -> fillna before astype(str)
    for column in ("timestamp", "sensor", "metric"):
        frame[column] = frame[column].fillna("").astype(str)
    if (frame["sensor"].str.strip() == "").any():
        raise RuleError("column 'sensor' contains empty values")
    if (frame["metric"].str.strip() == "").any():
        raise RuleError("column 'metric' contains empty values")

    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    if frame["value"].isna().any():
        count = int(frame["value"].isna().sum())
        raise RuleError(f"column 'value' contains {count} missing or "
                        f"non-numeric values")
    if not np_isfinite_all(frame["value"]):
        raise RuleError("column 'value' must be finite")

    try:
        epochs = [parse_ts(text) for text in frame["timestamp"]]
    except RuleError as exc:
        raise RuleError(f"column 'timestamp': {exc}") from exc
    if any(later < earlier for earlier, later in zip(epochs, epochs[1:])):
        raise RuleError("column 'timestamp' must be non-decreasing")

    frame = frame.reset_index(drop=True)
    return frame


def np_isfinite_all(series: pd.Series) -> bool:
    """Finite check without importing numpy into this module's API."""
    return all(math.isfinite(float(v)) for v in series)


def log_actuator(events: pd.DataFrame, path: str | Path) -> Path:
    """Write an actuator event log to CSV (creates parent directories)."""
    missing = [c for c in ACTUATOR_COLUMNS if c not in events.columns]
    if missing:
        raise RuleError(f"cannot log: missing column(s): "
                        f"{', '.join(missing)}")
    unknown = sorted(set(events["event"].fillna("").astype(str))
                     - set(EVENT_LABELS))
    if unknown:
        raise RuleError(f"cannot log: unknown event label(s): "
                        f"{', '.join(unknown)}")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(target, index=False)
    return target


def load_actuator_log(path: str | Path) -> pd.DataFrame:
    """Load and validate a previously written actuator event log."""
    source = Path(path)
    if not source.is_file():
        raise RuleError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise RuleError(f"could not parse {source.name}: {exc}") from exc
    missing = [c for c in ACTUATOR_COLUMNS if c not in frame.columns]
    if missing:
        raise RuleError(f"missing column(s): {', '.join(missing)} "
                        f"(expected {', '.join(ACTUATOR_COLUMNS)})")
    if frame.empty:
        raise RuleError(f"no rows in {source.name}")

    frame = frame.copy()
    # empty CSV cells -> NaN -> fillna before astype(str)
    for column in ACTUATOR_COLUMNS:
        frame[column] = frame[column].fillna("").astype(str)
    for column in ("rule", "actuator", "command"):
        if (frame[column].str.strip() == "").any():
            raise RuleError(f"column {column!r} contains empty values")
    unknown = sorted(set(frame["event"]) - set(EVENT_LABELS))
    if unknown:
        raise RuleError(f"column 'event' has unknown label(s): "
                        f"{', '.join(unknown)}")
    try:
        epochs = [parse_ts(text) for text in frame["timestamp"]]
    except RuleError as exc:
        raise RuleError(f"column 'timestamp': {exc}") from exc
    if any(later < earlier for earlier, later in zip(epochs, epochs[1:])):
        raise RuleError("column 'timestamp' must be non-decreasing")
    return frame.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# The engine
# --------------------------------------------------------------------------- #
@dataclass
class RuleState:
    """Mutable per-rule runtime state."""

    active: bool = False
    since: float | None = None
    triggers: int = 0
    releases: int = 0


class RuleEngine:
    """Replays sensor events through a rule set, emitting actuator events."""

    def __init__(self, rules: list[Rule]) -> None:
        if not rules:
            raise RuleError("no rules to run")
        self.rules = list(rules)
        self.states = {rule.id: RuleState() for rule in self.rules}

    def process(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Evaluate every event in order -> actuator log (chronological)."""
        missing = [c for c in EVENT_COLUMNS if c not in frame.columns]
        if missing:
            raise RuleError(f"missing column(s): {', '.join(missing)}")

        events: list[dict[str, str]] = []
        for row in frame.itertuples(index=False):
            try:
                timestamp = parse_ts(row.timestamp)
                value = float(row.value)
            except (ValueError, TypeError) as exc:
                raise RuleError(f"event value must be numeric: "
                                f"{row.value!r}") from exc
            if not math.isfinite(value):
                raise RuleError(f"event value must be finite: {value}")
            for rule in self.rules:
                if rule.sensor != row.sensor or rule.metric != row.metric:
                    continue
                state = self.states[rule.id]
                if not state.active:
                    if rule.condition(value):
                        if state.since is None:
                            state.since = timestamp
                        if timestamp - state.since >= rule.min_duration_s:
                            state.active = True
                            state.since = None
                            state.triggers += 1
                            events.append({
                                "timestamp": format_ts(timestamp),
                                "rule": rule.id, "event": "trigger",
                                "actuator": rule.actuator,
                                "command": rule.command,
                            })
                    else:
                        state.since = None
                elif rule.released(value):
                    state.active = False
                    state.since = None
                    state.releases += 1
                    if rule.release_command:
                        events.append({
                            "timestamp": format_ts(timestamp),
                            "rule": rule.id, "event": "release",
                            "actuator": rule.actuator,
                            "command": rule.release_command,
                        })
        return pd.DataFrame(events, columns=list(ACTUATOR_COLUMNS))


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report(rules: list[Rule], events: pd.DataFrame) -> str:
    """Human-readable rules + actuator log used by the CLI and demo."""
    lines = [
        "HOME AUTOMATION RULES - actuator event log",
        "=" * 78,
        f"Rules: {len(rules)}    Actuator events: {len(events)}",
        "",
        f"{'rule':<20} {'actuator':<16} {'event':<9} {'timestamp':<21} "
        f"command",
        "-" * 78,
    ]
    for _, row in events.iterrows():
        lines.append(f"{row['rule']:<20} {row['actuator']:<16} "
                     f"{row['event']:<9} {row['timestamp']:<21} "
                     f"{row['command']}")
    lines += ["", "Rules:"]
    for rule in rules:
        release = (f", release {rule.release_command}"
                   if rule.release_command else "")
        lines.append(
            f"  {rule.id}: {rule.sensor}/{rule.metric} {rule.op} "
            f"{rule.threshold:g} (hysteresis {rule.hysteresis:g}s, "
            f"min {rule.min_duration_s:g}s) -> "
            f"{rule.actuator} {rule.command}{release}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent.parent
DEMO_RULES = ROOT / "data" / "rules.json"
DEMO_EVENTS = ROOT / "data" / "events.csv"

EXPECTED_TRIGGERS = {
    "cool_living_room": 1,
    "heat_living_room": 1,
    "fan_humidity": 1,
    "lights_hallway": 4,
}


def run_demo(json_path: Path | None = None) -> int:
    """Replay the bundled events through the bundled rules - fully offline."""
    print("=" * 78)
    print(" HOME AUTOMATION RULES - offline demo")
    print(" Bundled JSON rules + event CSV; in-process engine; no network.")
    print("=" * 78)

    for bundled in (DEMO_RULES, DEMO_EVENTS):
        if not bundled.is_file():
            raise RuleError(f"bundled file not found: {bundled}")

    rules = load_rules(DEMO_RULES)
    events = load_events(DEMO_EVENTS)
    engine = RuleEngine(rules)
    actuator_log = engine.process(events)
    print(f"\nLoaded {len(rules)} rules and {len(events)} sensor events")

    # --- cross-checks the demo asserts ----------------------------------- #
    assert len(rules) == 4, "expected 4 bundled rules"
    assert len(actuator_log) == 14, "expected exactly 14 actuator events"

    triggers = (actuator_log[actuator_log["event"] == "trigger"]
                .groupby("rule").size().to_dict())
    assert triggers == EXPECTED_TRIGGERS, f"trigger counts: {triggers}"
    releases = (actuator_log[actuator_log["event"] == "release"]
                .groupby("rule").size().to_dict())
    assert releases == EXPECTED_TRIGGERS, f"release counts: {releases}"

    def moment(rule: str, kind: str) -> str:
        rows = actuator_log[(actuator_log["rule"] == rule)
                            & (actuator_log["event"] == kind)]
        return str(rows["timestamp"].iloc[0])

    # delay rules fire exactly min_duration after the condition starts
    assert moment("heat_living_room", "trigger") == "2026-03-01T00:06:00Z"
    assert moment("heat_living_room", "release") == "2026-03-01T00:07:00Z"
    assert moment("cool_living_room", "trigger") == "2026-03-01T00:12:00Z"
    assert moment("fan_humidity", "trigger") == "2026-03-01T00:06:00Z"
    # hysteresis: cool stays armed across the 25.0 plateau, releases at 23.0
    assert moment("cool_living_room", "release") == "2026-03-01T00:15:00Z"
    # zero-delay motion rule triggers and releases on each pulse
    light_starts = list(actuator_log[(actuator_log["rule"] == "lights_hallway")
                                     & (actuator_log["event"] == "trigger")]
                        ["timestamp"])
    assert light_starts == ["2026-03-01T00:01:30Z",
                            "2026-03-01T00:04:00Z",
                            "2026-03-01T00:10:00Z",
                            "2026-03-01T00:16:30Z"]

    # deterministic replay with a fresh engine
    replay = RuleEngine(rules).process(events)
    assert replay.equals(actuator_log), "replay is not deterministic"
    # every rule disarmed by the end of the log
    assert all(not state.active for state in engine.states.values()), \
        "a rule stayed active after the log ended"

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        written = log_actuator(actuator_log, Path(tmp) / "actuators.csv")
        assert load_actuator_log(written).equals(actuator_log), \
            "actuator log round-trip lost data"

    print()
    print(render_report(rules, actuator_log))

    if json_path is not None:
        payload = {
            "mode": "demo",
            "rules": len(rules),
            "sensor_events": len(events),
            "actuator_events": len(actuator_log),
            "triggers": {k: int(v) for k, v in triggers.items()},
        }
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote {json_path}")

    print("\nCross-checks OK: 4 rules, 14 actuator events, delay rules fire "
          "at +120s/+180s, hysteresis holds the cool rule armed, 4 motion "
          "pulses, deterministic replay, CSV round-trip")
    print("Demo completed successfully.")
    return 0
