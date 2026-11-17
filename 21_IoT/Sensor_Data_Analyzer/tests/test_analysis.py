"""Tests for the Sensor Data Analyzer project."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from analysis import (  # noqa: E402
    COLUMNS,
    DEFAULT_WINDOW,
    DEFAULT_Z,
    DROP_AT,
    FLAT_AT,
    FLAT_LENGTH,
    GAP_AT,
    GAP_LENGTH,
    METRIC,
    READINGS_FILE,
    SAMPLES,
    SENSORS,
    SPIKE_AT,
    START,
    AnalysisError,
    add_rolling,
    bundle_readings,
    correlation,
    detect_anomalies,
    detect_flatlines,
    detect_gaps,
    generate_readings,
    load_readings,
    render_report,
    resample_metric,
    run_demo,
    sensor_summary,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
READINGS = PROJECT_ROOT / "data" / "readings.csv"


@pytest.fixture(scope="module")
def frame():
    return load_readings(READINGS)


@pytest.fixture(scope="module")
def anomalies(frame):
    return detect_anomalies(frame)


def tiny(values: list[float], sensor: str = "s1",
         step_s: int = 60) -> pd.DataFrame:
    start = pd.Timestamp("2026-01-01T00:00:00Z")
    return pd.DataFrame({
        "timestamp": [start + pd.to_timedelta(step_s * i, unit="s")
                      for i in range(len(values))],
        "sensor": [sensor] * len(values),
        "metric": ["temperature"] * len(values),
        "value": values,
    })


# --------------------------------------------------------------------------- #
# Generated data
# --------------------------------------------------------------------------- #
def test_generate_readings_shape():
    data = generate_readings()
    assert list(data.columns) == list(COLUMNS)
    assert data["sensor"].nunique() == len(SENSORS)
    assert len(data) == len(SENSORS) * SAMPLES - GAP_LENGTH


def test_generate_readings_is_deterministic():
    assert generate_readings().equals(generate_readings())


def test_generate_readings_is_time_sorted():
    stamps = generate_readings()["timestamp"].tolist()
    assert stamps == sorted(stamps)


def test_bundle_readings_round_trip(tmp_path):
    path = bundle_readings(tmp_path / "readings.csv")
    assert path.is_file()
    reloaded = load_readings(path)
    assert len(reloaded) == len(generate_readings())


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def test_load_readings_types(frame):
    assert len(frame) == 355
    assert str(frame["timestamp"].dtype).startswith("datetime64")
    assert frame["value"].dtype.kind == "f"


def test_load_readings_missing_file(tmp_path):
    with pytest.raises(AnalysisError, match="readings not found"):
        load_readings(tmp_path / "ghost.csv")


def test_load_readings_missing_column(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("timestamp,sensor,value\n2026-01-01T00:00:00Z,a,1\n",
                    encoding="utf-8")
    with pytest.raises(AnalysisError, match="missing column"):
        load_readings(path)


def test_load_readings_rejects_non_numeric(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("timestamp,sensor,metric,value\n"
                    "2026-01-01T00:00:00Z,a,m,hot\n", encoding="utf-8")
    with pytest.raises(AnalysisError, match="non-numeric"):
        load_readings(path)


def test_load_readings_rejects_bad_timestamp(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("timestamp,sensor,metric,value\nnope,a,m,1\n",
                    encoding="utf-8")
    with pytest.raises(AnalysisError, match="timestamp"):
        load_readings(path)


def test_load_readings_rejects_empty_sensor(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("timestamp,sensor,metric,value\n"
                    "2026-01-01T00:00:00Z,,m,1\n", encoding="utf-8")
    with pytest.raises(AnalysisError, match="empty values"):
        load_readings(path)


def test_load_readings_rejects_empty_file(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("timestamp,sensor,metric,value\n", encoding="utf-8")
    with pytest.raises(AnalysisError, match="no rows"):
        load_readings(path)


# --------------------------------------------------------------------------- #
# Rolling statistics
# --------------------------------------------------------------------------- #
def test_add_rolling_adds_columns(frame):
    rolled = add_rolling(frame)
    assert {"rolling_mean", "rolling_std"} <= set(rolled.columns)


def test_add_rolling_first_row_has_nan(frame):
    rolled = add_rolling(frame, window=5)
    first = rolled.groupby("sensor").head(1)
    assert first["rolling_mean"].isna().all()


def test_add_rolling_stays_within_the_series(frame):
    rolled = add_rolling(frame, window=10).dropna()
    mask = (rolled["rolling_mean"] >= rolled.groupby("sensor")["value"]
            .transform("min"))
    assert mask.all()


def test_add_rolling_rejects_bad_window(frame):
    with pytest.raises(AnalysisError, match="window must be >= 2"):
        add_rolling(frame, window=1)


def test_add_rolling_rejects_empty():
    with pytest.raises(AnalysisError, match="no rows"):
        add_rolling(pd.DataFrame(columns=list(COLUMNS)))


def test_add_rolling_detects_a_step():
    data = tiny([20.0] * 20 + [30.0] * 5)
    rolled = add_rolling(data, window=5)
    assert rolled["rolling_mean"].iloc[-1] > rolled["rolling_mean"].iloc[5]


# --------------------------------------------------------------------------- #
# Anomalies
# --------------------------------------------------------------------------- #
def test_detect_anomalies_finds_injected_faults(anomalies):
    assert len(anomalies) >= 2
    pairs = {(row.sensor, str(row.timestamp))
             for row in anomalies.itertuples()}
    spike = pd.Timestamp(START) + pd.to_timedelta(60 * SPIKE_AT, unit="s")
    drop = pd.Timestamp(START) + pd.to_timedelta(60 * DROP_AT, unit="s")
    assert ("living_room", str(spike)) in pairs
    assert ("bedroom", str(drop)) in pairs


def test_detect_anomalies_columns(anomalies):
    assert list(anomalies.columns) == list(COLUMNS) + [
        "rolling_mean", "deviation", "z_score"]


def test_detect_anomalies_is_deterministic(frame):
    assert detect_anomalies(frame).equals(detect_anomalies(frame))


def test_detect_anomalies_threshold_matters(frame):
    strict = detect_anomalies(frame, z=10.0)
    loose = detect_anomalies(frame, z=1.5)
    assert len(strict) <= len(loose)


def test_detect_anomalies_on_a_clean_series_is_empty():
    data = tiny([20.0 + 0.01 * i for i in range(40)])
    assert detect_anomalies(data, z=4.0).empty


@pytest.mark.parametrize("z", [0.0, -1.0])
def test_detect_anomalies_rejects_bad_z(frame, z):
    with pytest.raises(AnalysisError, match="z must be > 0"):
        detect_anomalies(frame, z=z)


# --------------------------------------------------------------------------- #
# Gaps
# --------------------------------------------------------------------------- #
def test_detect_gaps_finds_the_hole(frame):
    gaps = detect_gaps(frame)
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.sensor == "bathroom"
    assert gap.missing == GAP_LENGTH
    assert gap.seconds == 60 * (GAP_LENGTH + 1)


def test_detect_gaps_after_timestamp(frame):
    gap = detect_gaps(frame)[0]
    expected = pd.Timestamp(START) + pd.to_timedelta(
        60 * (GAP_AT - 1), unit="s")
    assert gap.after == expected


def test_detect_gaps_none_on_regular_series():
    assert detect_gaps(tiny([1.0] * 10)) == []


def test_detect_gaps_respects_threshold():
    data = tiny([1.0] * 5, step_s=60)
    assert detect_gaps(data, max_gap_s=30) != []
    assert detect_gaps(data, max_gap_s=120) == []


def test_gap_to_dict_is_json_safe(frame):
    payload = detect_gaps(frame)[0].to_dict()
    json.dumps(payload)
    assert payload["missing"] == GAP_LENGTH


def test_detect_gaps_rejects_bad_threshold(frame):
    with pytest.raises(AnalysisError, match="max_gap_s must be > 0"):
        detect_gaps(frame, max_gap_s=0)


def test_detect_gaps_rejects_empty():
    with pytest.raises(AnalysisError, match="no rows"):
        detect_gaps(pd.DataFrame(columns=list(COLUMNS)))


# --------------------------------------------------------------------------- #
# Flatlines
# --------------------------------------------------------------------------- #
def test_detect_flatlines_finds_the_frozen_sensor(frame):
    runs = detect_flatlines(frame)
    assert runs
    longest = max(runs, key=lambda run: run["length"])
    assert longest["sensor"] == "living_room"
    assert longest["length"] == FLAT_LENGTH


def test_flatline_start_timestamp(frame):
    longest = max(detect_flatlines(frame), key=lambda run: run["length"])
    expected = pd.Timestamp(START) + pd.to_timedelta(60 * FLAT_AT, unit="s")
    assert longest["start"] == expected


def test_detect_flatlines_ignores_short_runs():
    data = tiny([20.0, 20.0, 21.0, 21.0, 22.0, 22.0])
    assert detect_flatlines(data, min_run=3) == []
    assert detect_flatlines(data, min_run=2) != []


def test_detect_flatlines_handles_multiple_runs():
    data = tiny([1.0, 1.0, 1.0, 2.0, 3.0, 3.0, 3.0, 4.0])
    runs = detect_flatlines(data, min_run=3)
    assert [run["length"] for run in runs] == [3, 3]


def test_detect_flatlines_rejects_bad_run(frame):
    with pytest.raises(AnalysisError, match="min_run must be >= 2"):
        detect_flatlines(frame, min_run=1)


def test_detect_flatlines_rejects_empty():
    with pytest.raises(AnalysisError, match="no rows"):
        detect_flatlines(pd.DataFrame(columns=list(COLUMNS)))


# --------------------------------------------------------------------------- #
# Resampling and summaries
# --------------------------------------------------------------------------- #
def test_resample_metric_bins(frame):
    table = resample_metric(frame, "living_room", METRIC, rule="10min")
    assert len(table) == SAMPLES // 10
    assert list(table.columns) == ["mean", "count"]


def test_resample_metric_conserves_rows(frame):
    table = resample_metric(frame, "living_room", METRIC, rule="10min")
    assert int(table["count"].sum()) == \
        len(frame[frame["sensor"] == "living_room"])


def test_resample_metric_mean_is_sane(frame):
    table = resample_metric(frame, "bedroom", METRIC, rule="30min")
    assert table["mean"].between(15.0, 25.0).all()


def test_resample_metric_unknown_sensor(frame):
    with pytest.raises(AnalysisError, match="no rows for"):
        resample_metric(frame, "cellar", METRIC)


def test_resample_metric_rejects_empty_rule(frame):
    with pytest.raises(AnalysisError, match="non-empty pandas offset"):
        resample_metric(frame, "living_room", METRIC, rule="")


def test_sensor_summary_rows(frame):
    summary = sensor_summary(frame)
    assert len(summary) == len(SENSORS)
    assert set(summary["sensor"]) == set(SENSORS)


def test_sensor_summary_counts(frame):
    summary = sensor_summary(frame).set_index("sensor")
    assert int(summary.loc["bathroom", "count"]) == SAMPLES - GAP_LENGTH
    assert int(summary.loc["bedroom", "count"]) == SAMPLES


def test_sensor_summary_bounds(frame):
    summary = sensor_summary(frame)
    assert (summary["min"] <= summary["mean"]).all()
    assert (summary["mean"] <= summary["max"]).all()


def test_sensor_summary_rejects_empty():
    with pytest.raises(AnalysisError, match="no rows"):
        sensor_summary(pd.DataFrame(columns=list(COLUMNS)))


# --------------------------------------------------------------------------- #
# Correlation
# --------------------------------------------------------------------------- #
def test_correlation_is_square(frame):
    corr = correlation(frame)
    assert corr.shape == (len(SENSORS), len(SENSORS))


def test_correlation_diagonal_is_one(frame):
    corr = correlation(frame)
    assert np.allclose(np.diag(corr.to_numpy()), 1.0)


def test_correlation_is_symmetric(frame):
    corr = correlation(frame)
    assert np.allclose(corr.to_numpy(), corr.to_numpy().T)


def test_correlation_unknown_metric(frame):
    with pytest.raises(AnalysisError, match="no rows for metric"):
        correlation(frame, metric="pressure")


def test_correlation_needs_two_sensors(frame):
    single = frame[frame["sensor"] == "bedroom"]
    with pytest.raises(AnalysisError, match="at least two sensors"):
        correlation(single)


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def test_render_report_contains_sections(frame, anomalies):
    report = render_report(frame, anomalies, detect_gaps(frame),
                           detect_flatlines(frame))
    assert "SENSOR DATA ANALYZER" in report
    assert "Anomalies:" in report
    assert "Gaps:" in report
    assert "Flatlines:" in report


def test_render_report_without_faults(frame):
    report = render_report(frame.head(10), detect_anomalies(frame.head(10)),
                           [], [])
    assert "SENSOR DATA ANALYZER" in report
    # the section headers only appear when there is something to report
    assert report.count("Gaps:") == 1
    assert report.count("Flatlines:") == 1


# --------------------------------------------------------------------------- #
# Demo and CLI
# --------------------------------------------------------------------------- #
def test_run_demo_prints_cross_checks(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    first = capsys.readouterr().out
    assert run_demo() == 0
    assert capsys.readouterr().out == first


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


def test_cli_reports_on_csv(capsys):
    assert main(["--readings", str(READINGS)]) == 0
    out = capsys.readouterr().out
    assert "SENSOR DATA ANALYZER" in out
    assert "Correlation" in out


def test_cli_resample_view(capsys):
    assert main(["--readings", str(READINGS),
                 "--resample", "living_room:10min"]) == 0
    assert "Resampled living_room" in capsys.readouterr().out


@pytest.mark.parametrize("args,needle", [
    (["--window", "1"], "window must be >= 2"),
    (["--z", "0"], "z must be > 0"),
    (["--resample", "living_room"], "--resample expects SENSOR:RULE"),
])
def test_cli_validates_flags(args, needle, capsys):
    assert main(["--readings", str(READINGS)] + args) == 2
    assert needle in capsys.readouterr().err


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--readings", str(tmp_path / "nope.csv")]) == 2
    assert "readings not found" in capsys.readouterr().err


def test_cli_json_export(tmp_path, capsys):
    out = tmp_path / "report.json"
    assert main(["--readings", str(READINGS), "--json", str(out),
                 "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["rows"] == 355
    assert payload["sensors"] == 3
    assert len(payload["anomalies"]) >= 2
    assert payload["gaps"][0]["missing"] == GAP_LENGTH
    assert capsys.readouterr().out == ""


def test_bundled_readings_exist():
    assert READINGS_FILE.is_file()
    assert DEFAULT_WINDOW >= 2
    assert math.isfinite(DEFAULT_Z)
