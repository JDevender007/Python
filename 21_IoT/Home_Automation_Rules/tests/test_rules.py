"""Tests for the Home Automation Rules engine."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from rules import (  # noqa: E402
    ACTUATOR_COLUMNS,
    DEMO_EVENTS,
    DEMO_RULES,
    EVENT_COLUMNS,
    EXPECTED_TRIGGERS,
    Rule,
    RuleEngine,
    RuleError,
    format_ts,
    load_actuator_log,
    load_events,
    load_rules,
    log_actuator,
    parse_rules,
    parse_ts,
    render_report,
    run_demo,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RULES_FILE = PROJECT_ROOT / "data" / "rules.json"
EVENTS_FILE = PROJECT_ROOT / "data" / "events.csv"

BASE_RULE = {
    "id": "demo_rule",
    "sensor": "living_room",
    "metric": "temperature",
    "condition": {"op": ">", "threshold": 20.0},
    "action": {"actuator": "heater", "command": "on"},
}


def make_rule(**overrides) -> dict:
    rule = json.loads(json.dumps(BASE_RULE))
    rule.update(overrides)
    return rule


def frame(rows: list[tuple[str, str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=list(EVENT_COLUMNS))


@pytest.fixture(scope="module")
def rules() -> list[Rule]:
    return load_rules(RULES_FILE)


@pytest.fixture(scope="module")
def events() -> pd.DataFrame:
    return load_events(EVENTS_FILE)


# --------------------------------------------------------------------------- #
# Timestamps
# --------------------------------------------------------------------------- #
def test_format_ts_is_iso_z():
    assert format_ts(0) == "1970-01-01T00:00:00Z"


def test_parse_ts_round_trip():
    assert format_ts(parse_ts("2026-03-01T00:06:00Z")) == "2026-03-01T00:06:00Z"


def test_parse_ts_accepts_lowercase_z():
    assert parse_ts("2026-03-01T00:00:00z") == parse_ts("2026-03-01T00:00:00Z")


def test_parse_ts_accepts_offsets():
    assert parse_ts("2026-03-01T00:00:00+00:00") == \
        parse_ts("2026-03-01T00:00:00Z")


def test_parse_ts_rejects_garbage():
    with pytest.raises(RuleError, match="invalid timestamp"):
        parse_ts("not-a-time")


# --------------------------------------------------------------------------- #
# Rule conditions
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("op,value,expected", [
    (">", 21.0, True),
    (">", 20.0, False),
    (">=", 20.0, True),
    ("<", 19.0, True),
    ("<", 20.0, False),
    ("<=", 20.0, True),
])
def test_condition_operators(op, value, expected):
    rule = Rule(id="r", sensor="s", metric="m", op=op, threshold=20.0,
                actuator="a", command="c")
    assert rule.condition(value) is expected


@pytest.mark.parametrize("op,value,expected", [
    (">", 18.0, True),
    (">", 19.1, False),
    (">=", 19.0, False),
    ("<", 21.0, True),
    ("<", 20.0, False),
    ("<=", 20.0, False),
])
def test_released_uses_hysteresis(op, value, expected):
    rule = Rule(id="r", sensor="s", metric="m", op=op, threshold=20.0,
                hysteresis=1.0, actuator="a", command="c")
    assert rule.released(value) is expected


# --------------------------------------------------------------------------- #
# Rule parsing
# --------------------------------------------------------------------------- #
def test_parse_rules_reads_one_rule():
    parsed = parse_rules({"rules": [BASE_RULE]})
    assert len(parsed) == 1
    assert parsed[0].id == "demo_rule"
    assert parsed[0].threshold == 20.0


def test_parse_rules_reads_optional_fields():
    parsed = parse_rules({"rules": [make_rule(hysteresis=2.0,
                                              min_duration_s=30,
                                              release={"command": "off"})]})
    assert parsed[0].hysteresis == 2.0
    assert parsed[0].min_duration_s == 30
    assert parsed[0].release_command == "off"


def test_parse_rules_rejects_non_object():
    with pytest.raises(RuleError, match="rules file must be a JSON object"):
        parse_rules([])


def test_parse_rules_rejects_missing_list():
    with pytest.raises(RuleError, match="missing top-level 'rules'"):
        parse_rules({})


def test_parse_rules_rejects_empty_list():
    with pytest.raises(RuleError, match="rules list is empty"):
        parse_rules({"rules": []})


def test_parse_rules_rejects_non_dict_rule():
    with pytest.raises(RuleError, match="must be an object"):
        parse_rules({"rules": ["nope"]})


@pytest.mark.parametrize("field", ["id", "sensor", "metric", "condition",
                                   "action"])
def test_parse_rules_rejects_missing_field(field):
    rule = make_rule()
    del rule[field]
    with pytest.raises(RuleError, match=f"missing field '{field}'"):
        parse_rules({"rules": [rule]})


def test_parse_rules_rejects_unknown_field():
    with pytest.raises(RuleError, match="unknown field"):
        parse_rules({"rules": [make_rule(colour="red")]})


def test_parse_rules_rejects_duplicate_ids():
    with pytest.raises(RuleError, match="duplicate rule id"):
        parse_rules({"rules": [BASE_RULE, BASE_RULE]})


def test_parse_rules_rejects_bad_operator():
    with pytest.raises(RuleError, match="invalid op"):
        parse_rules({"rules": [make_rule(
            condition={"op": "~", "threshold": 1.0})]})


def test_parse_rules_rejects_non_numeric_threshold():
    with pytest.raises(RuleError, match="threshold must be a finite number"):
        parse_rules({"rules": [make_rule(
            condition={"op": ">", "threshold": "hot"})]})


def test_parse_rules_rejects_negative_hysteresis():
    with pytest.raises(RuleError, match="hysteresis must be >= 0"):
        parse_rules({"rules": [make_rule(hysteresis=-1)]})


def test_parse_rules_rejects_negative_duration():
    with pytest.raises(RuleError, match="min_duration_s must be >= 0"):
        parse_rules({"rules": [make_rule(min_duration_s=-5)]})


def test_parse_rules_rejects_empty_command():
    with pytest.raises(RuleError, match="action.command"):
        parse_rules({"rules": [make_rule(
            action={"actuator": "heater", "command": " "})]})


def test_parse_rules_rejects_release_without_command():
    with pytest.raises(RuleError, match="release.command"):
        parse_rules({"rules": [make_rule(release={})]})


def test_load_rules_missing_file(tmp_path):
    with pytest.raises(RuleError, match="file not found"):
        load_rules(tmp_path / "ghost.json")


def test_load_rules_rejects_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{nope", encoding="utf-8")
    with pytest.raises(RuleError, match="invalid JSON"):
        load_rules(path)


def test_bundled_rules_load(rules):
    assert len(rules) == 4
    assert {rule.id for rule in rules} == set(EXPECTED_TRIGGERS)


# --------------------------------------------------------------------------- #
# Event loading
# --------------------------------------------------------------------------- #
def test_load_events_reads_the_csv(events):
    assert len(events) == 111
    assert list(events.columns) == list(EVENT_COLUMNS)


def test_load_events_missing_file(tmp_path):
    with pytest.raises(RuleError, match="file not found"):
        load_events(tmp_path / "ghost.csv")


def test_load_events_rejects_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("timestamp,sensor,value\n2026-01-01T00:00:00Z,a,1\n",
                    encoding="utf-8")
    with pytest.raises(RuleError, match="missing column"):
        load_events(path)


def test_load_events_rejects_non_numeric_values(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("timestamp,sensor,metric,value\n"
                    "2026-01-01T00:00:00Z,a,m,hot\n", encoding="utf-8")
    with pytest.raises(RuleError, match="non-numeric"):
        load_events(path)


def test_load_events_rejects_unsorted_timestamps(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("timestamp,sensor,metric,value\n"
                    "2026-01-01T00:01:00Z,a,m,1\n"
                    "2026-01-01T00:00:00Z,a,m,1\n", encoding="utf-8")
    with pytest.raises(RuleError, match="non-decreasing"):
        load_events(path)


def test_load_events_rejects_empty_sensor(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("timestamp,sensor,metric,value\n"
                    "2026-01-01T00:00:00Z,,m,1\n", encoding="utf-8")
    with pytest.raises(RuleError, match="empty values"):
        load_events(path)


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
def test_engine_triggers_immediately_without_delay():
    rule = Rule(id="r", sensor="s", metric="m", op=">", threshold=5.0,
                actuator="a", command="on", release_command="off")
    log = RuleEngine([rule]).process(frame([
        ("2026-01-01T00:00:00Z", "s", "m", 6.0),
        ("2026-01-01T00:01:00Z", "s", "m", 4.0),
    ]))
    assert list(log["event"]) == ["trigger", "release"]
    assert list(log["command"]) == ["on", "off"]


def test_engine_waits_for_min_duration():
    rule = Rule(id="r", sensor="s", metric="m", op=">", threshold=5.0,
                min_duration_s=120, actuator="a", command="on")
    log = RuleEngine([rule]).process(frame([
        ("2026-01-01T00:00:00Z", "s", "m", 6.0),
        ("2026-01-01T00:01:00Z", "s", "m", 6.0),
        ("2026-01-01T00:02:00Z", "s", "m", 6.0),
    ]))
    assert list(log["event"]) == ["trigger"]
    assert log["timestamp"].iloc[0] == "2026-01-01T00:02:00Z"


def test_engine_resets_duration_when_condition_drops():
    rule = Rule(id="r", sensor="s", metric="m", op=">", threshold=5.0,
                min_duration_s=120, actuator="a", command="on")
    log = RuleEngine([rule]).process(frame([
        ("2026-01-01T00:00:00Z", "s", "m", 6.0),
        ("2026-01-01T00:01:00Z", "s", "m", 4.0),
        ("2026-01-01T00:02:00Z", "s", "m", 6.0),
        ("2026-01-01T00:04:00Z", "s", "m", 6.0),
    ]))
    assert log["timestamp"].iloc[0] == "2026-01-01T00:04:00Z"


def test_engine_ignores_other_sensors():
    rule = Rule(id="r", sensor="s", metric="m", op=">", threshold=0.0,
                actuator="a", command="on")
    log = RuleEngine([rule]).process(frame([
        ("2026-01-01T00:00:00Z", "other", "m", 9.0),
    ]))
    assert log.empty


def test_engine_does_not_retrigger_while_active():
    rule = Rule(id="r", sensor="s", metric="m", op=">", threshold=5.0,
                actuator="a", command="on")
    log = RuleEngine([rule]).process(frame([
        ("2026-01-01T00:00:00Z", "s", "m", 6.0),
        ("2026-01-01T00:01:00Z", "s", "m", 9.0),
        ("2026-01-01T00:02:00Z", "s", "m", 8.0),
    ]))
    assert len(log) == 1


def test_engine_release_without_command_emits_nothing():
    rule = Rule(id="r", sensor="s", metric="m", op=">", threshold=5.0,
                actuator="a", command="on")
    log = RuleEngine([rule]).process(frame([
        ("2026-01-01T00:00:00Z", "s", "m", 6.0),
        ("2026-01-01T00:01:00Z", "s", "m", 1.0),
    ]))
    assert list(log["event"]) == ["trigger"]


def test_engine_rejects_empty_rule_set():
    with pytest.raises(RuleError, match="no rules"):
        RuleEngine([])


def test_engine_rejects_missing_event_columns():
    with pytest.raises(RuleError, match="missing column"):
        RuleEngine([Rule(id="r", sensor="s", metric="m", op=">", threshold=1.0,
                         actuator="a", command="c")]).process(
            pd.DataFrame({"timestamp": ["2026-01-01T00:00:00Z"]}))


def test_engine_rejects_non_numeric_event_value():
    with pytest.raises(RuleError, match="must be numeric"):
        RuleEngine([Rule(id="r", sensor="s", metric="m", op=">", threshold=1.0,
                         actuator="a", command="c")]).process(
            pd.DataFrame({"timestamp": ["2026-01-01T00:00:00Z"], "sensor": ["s"],
                          "metric": ["m"], "value": ["hot"]}))


def test_bundled_run_produces_fourteen_events(rules, events):
    log = RuleEngine(rules).process(events)
    assert len(log) == 14
    assert list(log.columns) == list(ACTUATOR_COLUMNS)


def test_bundled_trigger_counts(rules, events):
    log = RuleEngine(rules).process(events)
    counts = (log[log["event"] == "trigger"].groupby("rule").size()
              .to_dict())
    assert {key: int(value) for key, value in counts.items()} == \
        EXPECTED_TRIGGERS


def test_bundled_delay_rules_fire_at_expected_times(rules, events):
    log = RuleEngine(rules).process(events)
    heat = log[(log["rule"] == "heat_living_room")
               & (log["event"] == "trigger")]
    assert heat["timestamp"].iloc[0] == "2026-03-01T00:06:00Z"


def test_bundled_hysteresis_holds_cool_rule(rules, events):
    log = RuleEngine(rules).process(events)
    release = log[(log["rule"] == "cool_living_room")
                  & (log["event"] == "release")]
    assert release["timestamp"].iloc[0] == "2026-03-01T00:15:00Z"


def test_bundled_replay_is_deterministic(rules, events):
    first = RuleEngine(rules).process(events)
    second = RuleEngine(rules).process(events)
    assert first.equals(second)


def test_every_rule_is_disarmed_at_the_end(rules, events):
    engine = RuleEngine(rules)
    engine.process(events)
    assert all(not state.active for state in engine.states.values())


# --------------------------------------------------------------------------- #
# Logging and reporting
# --------------------------------------------------------------------------- #
def test_log_actuator_round_trip(tmp_path, rules, events):
    log = RuleEngine(rules).process(events)
    written = log_actuator(log, tmp_path / "out" / "actuators.csv")
    assert written.is_file()
    assert load_actuator_log(written).equals(log)


def test_log_actuator_creates_parents(tmp_path, rules, events):
    log = RuleEngine(rules).process(events)
    written = log_actuator(log, tmp_path / "a" / "b" / "log.csv")
    assert written.exists()


def test_log_actuator_rejects_unknown_event(rules, events):
    log = RuleEngine(rules).process(events).copy()
    log.loc[0, "event"] = "explode"
    with pytest.raises(RuleError, match="unknown event label"):
        log_actuator(log, Path("ignored.csv"))


def test_load_actuator_log_rejects_missing_column(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("timestamp,rule,event\n2026-01-01T00:00:00Z,r,trigger\n",
                    encoding="utf-8")
    with pytest.raises(RuleError, match="missing column"):
        load_actuator_log(path)


def test_render_report_lists_rules(rules, events):
    log = RuleEngine(rules).process(events)
    report = render_report(rules, log)
    assert "HOME AUTOMATION RULES" in report
    assert "cool_living_room" in report
    assert "thermostat" in report


# --------------------------------------------------------------------------- #
# Demo and CLI
# --------------------------------------------------------------------------- #
def test_run_demo_prints_cross_checks(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_run_demo_writes_json(tmp_path, capsys):
    target = tmp_path / "run.json"
    assert run_demo(target) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["actuator_events"] == 14
    assert payload["triggers"]["lights_hallway"] == 4
    assert "Cross-checks OK" in capsys.readouterr().out


def test_cli_demo(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_requires_a_mode():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_cli_requires_events(capsys):
    assert main(["--rules", str(RULES_FILE)]) == 2
    assert "--events is required" in capsys.readouterr().err


def test_cli_replays_and_writes_log(tmp_path, capsys):
    out = tmp_path / "actuators.csv"
    assert main(["--rules", str(RULES_FILE), "--events", str(EVENTS_FILE),
                 "--out", str(out)]) == 0
    assert out.is_file()
    assert "Actuator events : 14" in capsys.readouterr().out


def test_cli_missing_rules(tmp_path, capsys):
    assert main(["--rules", str(tmp_path / "nope.json"),
                 "--events", str(EVENTS_FILE)]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_json_summary(tmp_path, capsys):
    out = tmp_path / "run.json"
    assert main(["--rules", str(RULES_FILE), "--events", str(EVENTS_FILE),
                 "--json", str(out), "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["rules"] == 4
    assert payload["sensor_events"] == 111
    assert payload["triggers"]["fan_humidity"] == 1
    assert capsys.readouterr().out == ""


def test_bundled_files_exist():
    assert DEMO_RULES.is_file() and DEMO_EVENTS.is_file()
