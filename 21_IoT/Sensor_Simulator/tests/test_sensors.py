"""Tests for the Sensor Simulator project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sensors import (  # noqa: E402
    DEFAULT_FLEET,
    DEMO_CSV,
    FAULT_TYPES,
    REQUIRED_COLUMNS,
    SENSOR_KINDS,
    FaultSpec,
    SensorError,
    SensorSpec,
    default_fleet,
    format_ts,
    load_log,
    log_readings,
    parse_fault,
    parse_ts,
    run_demo,
    simulate,
    summarize,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _write(tmp_path: Path, text: str, name: str = "log.csv") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _frame_csv(tmp_path: Path, frame: pd.DataFrame,
               name: str = "log.csv") -> Path:
    path = tmp_path / name
    frame.to_csv(path, index=False)
    return path


# --------------------------------------------------------------------------- #
# Timestamps
# --------------------------------------------------------------------------- #
def test_timestamp_roundtrip():
    assert format_ts(1772323200) == "2026-03-01T00:00:00Z"
    assert parse_ts(format_ts(1772323200)) == 1772323200


def test_timestamp_rejects_garbage():
    with pytest.raises(SensorError, match="invalid timestamp"):
        parse_ts("yesterday-ish")


# --------------------------------------------------------------------------- #
# Fleet configuration
# --------------------------------------------------------------------------- #
def test_default_fleet_filter():
    assert len(DEFAULT_FLEET) == 3
    assert {spec.kind for spec in DEFAULT_FLEET} == set(SENSOR_KINDS)
    motion = default_fleet("motion")
    assert motion and all(spec.kind == "motion" for spec in motion)


def test_default_fleet_unknown_kind():
    with pytest.raises(SensorError, match="unknown sensor kind"):
        default_fleet("barometer")


# --------------------------------------------------------------------------- #
# Fault parsing
# --------------------------------------------------------------------------- #
def test_parse_fault_ok():
    fault = parse_fault("living_room_temp:spike:30:33")
    assert fault == FaultSpec("living_room_temp", "spike", 30, 33)


def test_parse_fault_wrong_part_count():
    with pytest.raises(SensorError, match="SENSOR:KIND:START:END"):
        parse_fault("spike:30:33")


def test_parse_fault_non_integer_ticks():
    with pytest.raises(SensorError, match="integers"):
        parse_fault("living_room_temp:spike:soon:33")


def test_parse_fault_unknown_kind():
    with pytest.raises(SensorError, match="unknown fault kind"):
        parse_fault("living_room_temp:meltdown:0:3")


def test_parse_fault_window_inverted():
    with pytest.raises(SensorError, match="before start"):
        parse_fault("living_room_temp:spike:9:3")


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #
def test_simulate_row_count_and_columns():
    frame = simulate()
    assert len(frame) == 3 * 48
    assert list(frame.columns) == list(REQUIRED_COLUMNS)
    assert set(frame["kind"]) == set(SENSOR_KINDS)


def test_simulate_is_deterministic_and_seed_sensitive():
    first = simulate(seed=42)
    second = simulate(seed=42)
    other = simulate(seed=7)
    assert first.equals(second)
    assert not first["value"].equals(other["value"])


def test_simulate_timestamps_spacing():
    frame = simulate(ticks=10, interval_s=2.0)
    temp = frame[frame["sensor"] == "living_room_temp"]
    epochs = temp["timestamp"].map(parse_ts).to_numpy(dtype=float)
    assert np.allclose(np.diff(epochs), 2.0)


def test_simulate_rejects_zero_ticks():
    with pytest.raises(SensorError, match="ticks must be >= 1"):
        simulate(ticks=0)


def test_simulate_rejects_bad_interval():
    with pytest.raises(SensorError, match="interval must be > 0"):
        simulate(interval_s=0.0)


def test_simulate_rejects_negative_seed():
    with pytest.raises(SensorError, match="seed must be a non-negative"):
        simulate(seed=-1)


def test_simulate_rejects_unknown_kind():
    bad = SensorSpec("probe", "pressure")
    with pytest.raises(SensorError, match="unknown sensor kind"):
        simulate(specs=(bad,))


def test_simulate_rejects_duplicate_names():
    dup = SensorSpec("living_room_temp", "temperature")
    with pytest.raises(SensorError, match="duplicate sensor name"):
        simulate(specs=DEFAULT_FLEET + (dup,))


def test_simulate_unknown_fault_sensor():
    fault = FaultSpec("garage_temp", "spike", 0, 1)
    with pytest.raises(SensorError, match="unknown sensor"):
        simulate(faults=(fault,))


def test_simulate_fault_window_beyond_ticks():
    fault = FaultSpec("living_room_temp", "spike", 0, 999)
    with pytest.raises(SensorError, match="exceeds ticks"):
        simulate(ticks=5, faults=(fault,))


def test_simulate_rejects_overlapping_faults():
    first = FaultSpec("living_room_temp", "spike", 2, 6)
    second = FaultSpec("living_room_temp", "drift", 5, 9)
    with pytest.raises(SensorError, match="overlapping faults"):
        simulate(faults=(first, second))


def test_simulate_motion_stays_binary():
    pir = SensorSpec("pir", "motion", probability=0.3)
    frame = simulate(specs=(pir,), ticks=200)
    values = set(frame["value"])
    assert values <= {0.0, 1.0}
    assert values == {0.0, 1.0}


def test_simulate_humidity_is_clipped():
    humid = SensorSpec("hum", "humidity", base=95.0, amplitude=8.0,
                       noise_std=4.0)
    fault = FaultSpec("hum", "spike", 0, 0)
    frame = simulate(specs=(humid,), ticks=12, faults=(fault,))
    assert frame["value"].max() <= 100.0
    assert (frame["value"] == 100.0).any()


def test_simulate_spike_adds_exact_delta():
    clean = simulate()
    faulty = simulate(faults=(FaultSpec("living_room_temp", "spike",
                                        10, 12),))
    clean_temp = clean[clean["sensor"] == "living_room_temp"]["value"]
    spike = faulty[faulty["fault"] == "spike"]["value"]
    assert len(spike) == 3
    deltas = spike.to_numpy() - clean_temp.iloc[10:13].to_numpy()
    assert np.allclose(deltas, 15.0)
    assert (faulty["fault"] == "spike").sum() == 3
    assert (faulty["fault"] != "spike").sum() == len(faulty) - 3


def test_simulate_dropout_drops_rows():
    clean = simulate()
    faulty = simulate(faults=(FaultSpec("hallway_motion", "dropout",
                                        0, 2),))
    assert len(faulty) == len(clean) - 3
    assert (faulty["sensor"] == "hallway_motion").sum() == 45


def test_simulate_stuck_freezes_value():
    clean = simulate()
    faulty = simulate(faults=(FaultSpec("living_room_temp", "stuck",
                                        0, 5),))
    window = faulty[faulty["sensor"] == "living_room_temp"]["value"].iloc[:6]
    baseline = clean[clean["sensor"] == "living_room_temp"]["value"].iloc[:6]
    assert window.nunique() == 1
    assert window.iloc[0] == baseline.iloc[0]


def test_simulate_drift_accumulates_linearly():
    clean = simulate()
    faulty = simulate(faults=(FaultSpec("living_room_temp", "drift",
                                        5, 9),))
    clean_temp = clean[clean["sensor"] == "living_room_temp"]["value"]
    drift = faulty[faulty["fault"] == "drift"]["value"]
    deltas = drift.to_numpy() - clean_temp.iloc[5:10].to_numpy()
    assert np.allclose(deltas, [1.5, 3.0, 4.5, 6.0, 7.5])


# --------------------------------------------------------------------------- #
# CSV logging
# --------------------------------------------------------------------------- #
def test_log_and_load_roundtrip(tmp_path):
    frame = simulate(ticks=6)
    written = log_readings(frame, tmp_path / "out" / "log.csv")
    assert written.is_file()
    assert load_log(written).equals(frame)


def test_log_rejects_missing_columns(tmp_path):
    with pytest.raises(SensorError, match="missing column"):
        log_readings(pd.DataFrame({"value": [1.0]}), tmp_path / "x.csv")


def test_log_rejects_non_numeric_values(tmp_path):
    frame = simulate(ticks=4)
    frame["value"] = frame["value"].astype(object)
    frame.loc[0, "value"] = "warm"
    with pytest.raises(SensorError, match="'value' must be numeric"):
        log_readings(frame, tmp_path / "x.csv")


def test_load_missing_file(tmp_path):
    with pytest.raises(SensorError, match="file not found"):
        load_log(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = _write(tmp_path, "timestamp,value\n2026-03-01T00:00:00Z,1.0\n")
    with pytest.raises(SensorError, match="missing column"):
        load_log(path)


def test_load_empty_csv(tmp_path):
    header = ",".join(REQUIRED_COLUMNS) + "\n"
    with pytest.raises(SensorError, match="no rows"):
        load_log(_write(tmp_path, header))


def test_load_rejects_bad_values(tmp_path):
    good = "2026-03-01T00:00:00Z,probe,temperature,20.5,none"
    bad_text = (",".join(REQUIRED_COLUMNS) + "\n"
                + good + "\n"
                + "2026-03-01T00:00:05Z,probe,temperature,warm,none\n")
    with pytest.raises(SensorError, match="missing or non-numeric"):
        load_log(_write(tmp_path, bad_text, "warm.csv"))
    empty_cell = (",".join(REQUIRED_COLUMNS) + "\n"
                  + good + "\n"
                  + "2026-03-01T00:00:05Z,probe,temperature,,none\n")
    with pytest.raises(SensorError, match="missing or non-numeric"):
        load_log(_write(tmp_path, empty_cell, "empty.csv"))


def test_load_rejects_empty_sensor_cell(tmp_path):
    text = (",".join(REQUIRED_COLUMNS) + "\n"
            + "2026-03-01T00:00:00Z,,temperature,20.5,none\n")
    with pytest.raises(SensorError, match="contains empty values"):
        load_log(_write(tmp_path, text))


def test_load_rejects_unknown_labels(tmp_path):
    bad_kind = (",".join(REQUIRED_COLUMNS) + "\n"
                + "2026-03-01T00:00:00Z,probe,pressure,20.5,none\n")
    with pytest.raises(SensorError, match="unknown sensor kind"):
        load_log(_write(tmp_path, bad_kind, "kind.csv"))
    bad_fault = (",".join(REQUIRED_COLUMNS) + "\n"
                 + "2026-03-01T00:00:00Z,probe,temperature,20.5,meltdown\n")
    with pytest.raises(SensorError, match="unknown fault label"):
        load_log(_write(tmp_path, bad_fault, "fault.csv"))


def test_load_rejects_bad_timestamp(tmp_path):
    text = (",".join(REQUIRED_COLUMNS) + "\n"
            + "tomorrow,probe,temperature,20.5,none\n")
    with pytest.raises(SensorError, match="invalid timestamp"):
        load_log(_write(tmp_path, text))


def test_load_rejects_non_monotonic_timestamps(tmp_path):
    text = (",".join(REQUIRED_COLUMNS) + "\n"
            + "2026-03-01T00:00:05Z,probe,temperature,20.5,none\n"
            + "2026-03-01T00:00:00Z,probe,temperature,20.6,none\n")
    with pytest.raises(SensorError, match="non-decreasing"):
        load_log(_write(tmp_path, text))


def test_load_rejects_non_binary_motion(tmp_path):
    text = (",".join(REQUIRED_COLUMNS) + "\n"
            + "2026-03-01T00:00:00Z,pir,motion,0.5,none\n")
    with pytest.raises(SensorError, match="motion sensors must be 0 or 1"):
        load_log(_write(tmp_path, text))


# --------------------------------------------------------------------------- #
# Summaries
# --------------------------------------------------------------------------- #
def test_summarize_counts_every_reading():
    frame = simulate(faults=(FaultSpec("living_room_temp", "spike",
                                       30, 33),))
    table = summarize(frame)
    assert len(table) == 3
    assert int(table["readings"].sum()) == len(frame)
    assert (table["min"] <= table["mean"]).all()
    assert (table["mean"] <= table["max"]).all()
    faults = table.set_index("sensor")["faults"]
    assert int(faults["living_room_temp"]) == 4
    assert int(faults["hallway_motion"]) == 0


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out
    assert "Sensor summary:" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path, monkeypatch):
    monkeypatch.setattr("sensors.DEMO_CSV", tmp_path / "nope.csv")
    with pytest.raises(SensorError, match="bundled sample"):
        run_demo()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out
    assert "Virtual sensors, offline CSV logging" in out  # banner shown


def test_cli_log_writes_csv_and_json(tmp_path, capsys):
    log_path = tmp_path / "run.csv"
    json_path = tmp_path / "summary.json"
    code = main(["--log", str(log_path), "--ticks", "6",
                 "--fault", "living_room_temp:spike:2:3",
                 "--json", str(json_path), "--quiet"])
    assert code == 0
    assert log_path.is_file()
    frame = load_log(log_path)
    assert len(frame) == 18
    assert int((frame["fault"] == "spike").sum()) == 2
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["mode"] == "log" and payload["readings"] == 18
    assert len(payload["summary"]) == 3
    assert "Wrote 18 readings" in capsys.readouterr().out


def test_cli_sensor_filter(tmp_path):
    log_path = tmp_path / "motion.csv"
    assert main(["--log", str(log_path), "--sensor", "motion",
                 "--ticks", "5", "--quiet"]) == 0
    frame = load_log(log_path)
    assert set(frame["kind"]) == {"motion"}
    assert len(frame) == 5


def test_cli_replay(capsys):
    assert main(["--replay", str(DEMO_CSV)]) == 0
    out = capsys.readouterr().out
    assert "Sensor summary:" in out
    assert "Replayed 141 readings" in out


def test_cli_replay_missing_file(tmp_path, capsys):
    assert main(["--replay", str(tmp_path / "nope.csv")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_replay_invalid_csv(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main(["--replay", str(bad)]) == 2
    assert "missing column" in capsys.readouterr().err


def test_cli_bad_fault_format_fails_fast(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--log", str(tmp_path / "x.csv"), "--fault", "spike:30:33"])
    assert exc.value.code == 2
    assert "SENSOR:KIND:START:END" in capsys.readouterr().err


def test_cli_fault_beyond_ticks(tmp_path, capsys):
    code = main(["--log", str(tmp_path / "x.csv"), "--ticks", "5",
                 "--fault", "living_room_temp:spike:0:99", "--quiet"])
    assert code == 2
    assert "exceeds ticks" in capsys.readouterr().err


def test_cli_fault_not_allowed_with_demo(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--demo", "--fault", "living_room_temp:spike:0:1"])
    assert exc.value.code == 2
    assert "--fault only applies to --log" in capsys.readouterr().err


def test_cli_rejects_zero_ticks(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--log", "x.csv", "--ticks", "0"])
    assert exc.value.code == 2
    assert "--ticks must be >= 1" in capsys.readouterr().err


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    assert "--demo --log --replay is required" in capsys.readouterr().err


def test_cli_quiet_suppresses_banner(capsys):
    assert main(["--demo", "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "Virtual sensors, offline CSV logging" not in out
    assert "Demo completed successfully." in out


def test_project_has_bundled_sample():
    assert DEMO_CSV.is_file()
    assert DEMO_CSV.parent == PROJECT_ROOT / "data"
    assert set(FAULT_TYPES) >= {"none", "spike", "drift", "stuck", "dropout"}
