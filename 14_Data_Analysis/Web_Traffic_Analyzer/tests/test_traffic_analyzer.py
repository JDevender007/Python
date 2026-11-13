"""Tests for the Web Traffic Analyzer project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from traffic_analyzer import (  # noqa: E402
    DEMO_CSV,
    REQUIRED_COLUMNS,
    STATUS_CLASSES,
    TrafficError,
    analyze,
    format_bytes,
    load_traffic,
    render_report,
    run_demo,
    status_class,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _row(**overrides) -> dict:
    row = {
        "timestamp": "2025-06-01 10:00:00", "method": "GET", "path": "/",
        "status": 200, "bytes": 1000, "duration_ms": 100,
        "client_ip": "10.0.0.1", "session_id": "S-1",
    }
    row.update(overrides)
    return row


def _csv(tmp_path: Path, rows: list[dict], name: str = "access.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_traffic(DEMO_CSV)


@pytest.fixture(scope="module")
def report(sample):
    return analyze(sample, top=5)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 1664
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    assert sample["timestamp"].is_monotonic_increasing
    assert sample["path"].str.startswith("/").all()
    assert sample["status"].between(100, 599).all()
    assert set(sample["method"]) <= {"GET", "POST"}
    assert (sample["bytes"] >= 0).all() and (sample["duration_ms"] >= 0).all()


def test_load_missing_file(tmp_path):
    with pytest.raises(TrafficError, match="not found"):
        load_traffic(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("timestamp,path\n2025-06-01 10:00:00,/\n", encoding="utf-8")
    with pytest.raises(TrafficError, match="missing column"):
        load_traffic(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(TrafficError, match="no rows"):
        load_traffic(path)


def test_load_bad_timestamp(tmp_path):
    path = _csv(tmp_path, [_row(timestamp="yesterday")])
    with pytest.raises(TrafficError, match="unparseable timestamp"):
        load_traffic(path)


def test_load_unknown_method(tmp_path):
    path = _csv(tmp_path, [_row(method="FETCH")])
    with pytest.raises(TrafficError, match="unknown method.*FETCH"):
        load_traffic(path)


def test_load_method_case_normalized(tmp_path):
    path = _csv(tmp_path, [_row(method="get")])
    frame = load_traffic(path)
    assert frame["method"].iloc[0] == "GET"


def test_load_empty_path(tmp_path):
    path = _csv(tmp_path, [_row(path="")])
    with pytest.raises(TrafficError, match="empty path"):
        load_traffic(path)


def test_load_path_without_slash(tmp_path):
    path = _csv(tmp_path, [_row(path="about")])
    with pytest.raises(TrafficError, match="start with '/'"):
        load_traffic(path)


def test_load_status_non_numeric(tmp_path):
    path = _csv(tmp_path, [_row(status="OK")])
    with pytest.raises(TrafficError, match="non-numeric"):
        load_traffic(path)


def test_load_status_out_of_range(tmp_path):
    path = _csv(tmp_path, [_row(status=600)])
    with pytest.raises(TrafficError, match="100..599"):
        load_traffic(path)


def test_load_fractional_status(tmp_path):
    path = _csv(tmp_path, [_row(status=200.5)])
    with pytest.raises(TrafficError, match="whole numbers"):
        load_traffic(path)


def test_load_negative_bytes(tmp_path):
    path = _csv(tmp_path, [_row(bytes=-10)])
    with pytest.raises(TrafficError, match="non-negative"):
        load_traffic(path)


def test_load_negative_duration(tmp_path):
    path = _csv(tmp_path, [_row(duration_ms=-5)])
    with pytest.raises(TrafficError, match="non-negative"):
        load_traffic(path)


def test_load_empty_client_ip(tmp_path):
    path = _csv(tmp_path, [_row(client_ip=None)])
    with pytest.raises(TrafficError, match="empty 'client_ip'"):
        load_traffic(path)


def test_load_empty_session_id(tmp_path):
    path = _csv(tmp_path, [_row(session_id="  ")])
    with pytest.raises(TrafficError, match="empty 'session_id'"):
        load_traffic(path)


def test_load_sorts_by_timestamp(tmp_path):
    path = _csv(tmp_path, [
        _row(timestamp="2025-06-02 10:00:00", session_id="S-2"),
        _row(timestamp="2025-06-01 10:00:00", session_id="S-1"),
    ])
    frame = load_traffic(path)
    assert list(frame["session_id"]) == ["S-1", "S-2"]


# --------------------------------------------------------------------------- #
# Date-window filtering
# --------------------------------------------------------------------------- #
def test_since_filter(sample):
    day = load_traffic(DEMO_CSV, since="2025-06-03")
    assert len(day) < len(sample)
    assert (day["timestamp"] >= pd.Timestamp("2025-06-03")).all()
    assert day["timestamp"].min().date().isoformat() == "2025-06-03"


def test_until_filter_is_inclusive(sample):
    day = load_traffic(DEMO_CSV, until="2025-06-01")
    assert len(day) < len(sample)
    assert day["timestamp"].max() < pd.Timestamp("2025-06-02")
    assert day["timestamp"].min().date().isoformat() == "2025-06-01"


def test_since_until_window(sample):
    week = load_traffic(DEMO_CSV, since="2025-06-01", until="2025-06-07")
    assert week["timestamp"].min() >= pd.Timestamp("2025-06-01")
    assert week["timestamp"].max() < pd.Timestamp("2025-06-08")
    assert len(week) < len(sample)


def test_since_after_until_rejected(tmp_path):
    path = _csv(tmp_path, [_row()])
    with pytest.raises(TrafficError, match="since must be on or before"):
        load_traffic(path, since="2025-06-10", until="2025-06-01")


def test_window_with_no_rows(sample):
    with pytest.raises(TrafficError, match="no requests in the requested date range"):
        load_traffic(DEMO_CSV, since="2030-01-01")


def test_bad_date_format(sample):
    with pytest.raises(TrafficError, match="YYYY-MM-DD"):
        load_traffic(DEMO_CSV, since="june 1st")


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def test_analyze_totals(sample, report):
    assert report.requests == len(sample) == 1664
    assert report.unique_ips == sample["client_ip"].nunique()
    assert report.unique_sessions == sample["session_id"].nunique()
    assert report.bytes_total == int(sample["bytes"].sum())
    assert report.avg_duration_ms > 0
    assert report.requests_per_session > 1
    assert report.window_start <= report.window_end


def test_status_classes_partition(sample, report):
    assert sum(report.status_classes.values()) == report.requests
    manual = sample["status"].map(status_class).value_counts()
    for name in STATUS_CLASSES:
        assert report.status_classes[name] == int(manual.get(name, 0))
    assert report.error_rate_pct == pytest.approx(
        (report.status_classes["4xx"] + report.status_classes["5xx"])
        / report.requests * 100)


def test_error_rate_on_tiny_frame(tmp_path):
    rows = [_row(), _row(session_id="S-2"), _row(status=404, session_id="S-3"),
            _row(status=500, session_id="S-4")]
    report = analyze(load_traffic(_csv(tmp_path, rows)))
    assert report.error_rate_pct == pytest.approx(50.0)
    assert report.status_classes["2xx"] == 2
    assert report.status_classes["4xx"] == 1
    assert report.status_classes["5xx"] == 1
    assert report.status_classes["3xx"] == 0


def test_top_paths_math(sample, report):
    table = report.top_paths
    hits = list(table["hits"])
    assert hits == sorted(hits, reverse=True)
    assert table["hits"].sum() <= report.requests
    top_path = table.index[0]
    assert int(table.iloc[0]["hits"]) == int((sample["path"] == top_path).sum())
    assert table.iloc[0]["share_pct"] == pytest.approx(
        int(table.iloc[0]["hits"]) / report.requests * 100)


def test_slowest_paths_ordered(report):
    values = list(report.slowest_paths["avg_ms"])
    assert values == sorted(values, reverse=True)
    assert report.slowest_paths.iloc[0]["avg_ms"] >= report.top_paths["avg_ms"].max()


def test_top_ips(report):
    assert len(report.top_ips) == 5
    values = list(report.top_ips["requests"])
    assert values == sorted(values, reverse=True)


def test_hourly_profile(report):
    assert len(report.hourly) == 24
    assert int(report.hourly.sum()) == report.requests
    assert 0 <= report.peak_hour <= 23
    assert int(report.hourly.max()) == int(report.hourly.loc[report.peak_hour])


def test_daily_profile(report):
    assert int(report.daily.sum()) == report.requests
    assert len(report.daily) == 14


def test_analyze_rejects_bad_top(sample):
    with pytest.raises(TrafficError, match="top must be"):
        analyze(sample, top=0)


def test_report_to_dict(report):
    payload = report.to_dict()
    json.dumps(payload)
    assert payload["requests"] == 1664
    assert payload["status_classes"]["2xx"] > 1400
    assert len(payload["top_paths"]) == 5
    assert len(payload["hourly"]) == 24
    assert len(payload["daily"]) == 14
    assert payload["bytes_human"].endswith(("B", "KB", "MB", "GB"))


def test_format_bytes():
    assert format_bytes(0) == "0 B"
    assert format_bytes(1023) == "1023 B"
    assert format_bytes(1536) == "1.5 KB"
    assert format_bytes(5_000_000) == "4.8 MB"
    assert format_bytes(3 * 1024 ** 3).endswith("GB")


def test_status_class_buckets():
    assert status_class(200) == "2xx"
    assert status_class(301) == "3xx"
    assert status_class(404) == "4xx"
    assert status_class(500) == "5xx"


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def test_render_report_sections(report):
    text = render_report(report)
    assert "WEB TRAFFIC ANALYSIS" in text
    assert "Status classes:" in text
    assert "paths by hits:" in text
    assert "Slowest paths" in text
    assert "Hourly profile" in text
    assert "Top clients" in text
    assert "4xx" in text and "5xx" in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Filtered to 2025-06-01" in out
    assert "WEB TRAFFIC ANALYSIS" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(TrafficError, match="bundled sample"):
        run_demo(csv_path=tmp_path / "nope.csv")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_file_analysis(capsys):
    assert main(["--file", str(DEMO_CSV)]) == 0
    out = capsys.readouterr().out
    assert "WEB TRAFFIC ANALYSIS" in out and "Done." in out


def test_cli_top_option(capsys):
    assert main(["--file", str(DEMO_CSV), "--top", "3"]) == 0
    out = capsys.readouterr().out
    assert "Top 3 paths" in out and "Top clients" in out


def test_cli_date_window(capsys):
    assert main(["--file", str(DEMO_CSV), "--since", "2025-06-01",
                 "--until", "2025-06-01", "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "Done." in out


def test_cli_json_output(tmp_path, capsys):
    out_file = tmp_path / "report.json"
    assert main(["--file", str(DEMO_CSV), "--json", str(out_file)]) == 0
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["requests"] == 1664
    assert payload["unique_sessions"] == 643


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.csv")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_invalid_schema(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main(["--file", str(bad)]) == 2
    assert "missing column" in capsys.readouterr().err


def test_cli_bad_since(capsys):
    assert main(["--file", str(DEMO_CSV), "--since", "someday"]) == 2
    assert "YYYY-MM-DD" in capsys.readouterr().err


def test_cli_bad_top(capsys):
    assert main(["--file", str(DEMO_CSV), "--top", "0"]) == 2
    assert "--top" in capsys.readouterr().err


def test_cli_requires_source(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_project_has_sample_data():
    assert DEMO_CSV.is_file()
    assert DEMO_CSV.parent == PROJECT_ROOT / "data"
