"""Tests for the Log Monitor project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from logmonitor import (  # noqa: E402
    BUNDLED_LOGS,
    DEMO_MIN_SAMPLES,
    DEMO_THRESHOLD,
    EXPECTED_ALERTS,
    EXPECTED_RECORDS,
    EXPECTED_SERVICES,
    LEVELS,
    LogError,
    LogRecord,
    error_rate,
    load_bundled,
    parse_file,
    parse_line,
    parse_many,
    rate_by_minute,
    render_report,
    run_demo,
    summarize,
    threshold_alerts,
    top_offenders,
)
from main import build_parser, main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

STRUCTURED = ('2025-03-10 09:00:00 INFO service=api-gateway '
              'msg="GET /health 200 ok" duration=12ms')
UNSTRUCTURED = "2025-03-10 09:30:17 ERROR [payment-adapter] timeout upstream"


def _write(tmp_path: Path, text: str, name: str = "sample.log") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def test_parse_structured_line():
    record = parse_line(STRUCTURED)
    assert record.level == "INFO"
    assert record.service == "api-gateway"
    assert record.message == "GET /health 200 ok"
    assert record.timestamp.year == 2025
    assert ("duration", "12ms") in record.attributes
    assert not record.is_error


def test_parse_unstructured_line():
    record = parse_line(UNSTRUCTURED)
    assert record.level == "ERROR"
    assert record.service == "payment-adapter"
    assert record.message == "timeout upstream"
    assert record.attributes == ()
    assert record.is_error


def test_parse_line_normalisation():
    record = parse_line(f"   {STRUCTURED}   ")
    assert record.service == "api-gateway"
    assert record.minute == "2025-03-10 09:00"
    lower = parse_line(STRUCTURED.replace(" INFO ", " info "))
    assert lower.level == "INFO"


def test_parse_line_empty_raises():
    with pytest.raises(LogError, match="empty log line"):
        parse_line("   ")


def test_parse_line_missing_timestamp():
    with pytest.raises(LogError, match="missing timestamp"):
        parse_line("INFO service=api-gateway msg=\"hi\"")


def test_parse_line_unknown_level():
    with pytest.raises(LogError, match="unknown log level"):
        parse_line('2025-03-10 09:00:00 TRACE service=api msg="x"')


def test_parse_line_unknown_level_unstructured():
    with pytest.raises(LogError, match="unknown log level"):
        parse_line("2025-03-10 09:00:00 FATAL [api] boom")


def test_parse_line_known_level_bad_format():
    # level is valid but the rest matches neither format
    with pytest.raises(LogError, match="unrecognized line format"):
        parse_line("2025-03-10 09:00:00 INFO something unstructured")


def test_parse_line_all_level_constants_valid():
    for level in LEVELS:
        record = parse_line(
            f'2025-03-10 09:00:00 {level} service=svc msg="m"')
        assert record.level == level


# --------------------------------------------------------------------------- #
# File parsing
# --------------------------------------------------------------------------- #
def test_bundled_logs_exist():
    for path in BUNDLED_LOGS:
        assert path.is_file(), path
    assert BUNDLED_LOGS[0].parent == DATA_DIR


def test_parse_bundled_app_log():
    records, skipped = parse_file(DATA_DIR / "app.log")
    assert len(records) == 60
    assert skipped == 0
    services = {r.service for r in records}
    assert services == {"api-gateway", "billing", "auth", "worker"}


def test_parse_bundled_legacy_log():
    records, skipped = parse_file(DATA_DIR / "legacy.log")
    assert len(records) == 20
    assert skipped == 0
    assert {r.service for r in records} == {"payment-adapter", "cache"}


def test_load_bundled_totals():
    records, skipped = load_bundled()
    assert len(records) == EXPECTED_RECORDS
    assert skipped == 0
    assert {r.service for r in records} == EXPECTED_SERVICES


def test_parse_file_missing(tmp_path):
    with pytest.raises(LogError, match="file not found"):
        parse_file(tmp_path / "nope.log")


def test_parse_file_empty_or_blank(tmp_path):
    records, skipped = parse_file(_write(tmp_path, ""))
    assert records == [] and skipped == 0
    records, skipped = parse_file(_write(tmp_path, f"\n\n{STRUCTURED}\n\n"))
    assert len(records) == 1 and skipped == 0


def test_parse_file_strict_bad_line(tmp_path):
    path = _write(tmp_path, f"{STRUCTURED}\nthis is garbage\n")
    with pytest.raises(LogError, match="missing timestamp"):
        parse_file(path, strict=True)


def test_parse_file_lenient_counts_skipped(tmp_path):
    path = _write(tmp_path, f"{STRUCTURED}\ngarbage line\n{UNSTRUCTURED}\n")
    records, skipped = parse_file(path, strict=False)
    assert len(records) == 2
    assert skipped == 1


def test_parse_file_strict_unknown_level(tmp_path):
    path = _write(tmp_path, "2025-03-10 09:00:00 BOGUS [svc] msg\n")
    with pytest.raises(LogError, match="unknown log level"):
        parse_file(path, strict=True)


def test_parse_many_combines_files(tmp_path):
    first = _write(tmp_path, f"{STRUCTURED}\n", "a.log")
    second = _write(tmp_path, f"{UNSTRUCTURED}\n", "b.log")
    records, skipped = parse_many([first, second])
    assert len(records) == 2 and skipped == 0
    assert [r.service for r in records] == ["api-gateway", "payment-adapter"]
    with pytest.raises(LogError, match="file not found"):
        parse_many([tmp_path / "gone.log"])


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def _records(lines: list[str]) -> list[LogRecord]:
    return [parse_line(line) for line in lines]


def test_error_rate_empty_is_zero():
    assert error_rate([]) == 0.0


def test_error_rate_counts_errors_and_critical():
    lines = [
        '2025-03-10 09:00:00 INFO service=a msg="ok"',
        '2025-03-10 09:00:01 ERROR service=a msg="bad"',
        '2025-03-10 09:00:02 CRITICAL service=a msg="worse"',
        '2025-03-10 09:00:03 WARNING service=a msg="meh"',
    ]
    assert error_rate(_records(lines)) == 0.5


def test_summarize_per_service_totals():
    records, _ = load_bundled()
    summaries = summarize(records)
    assert set(summaries) == EXPECTED_SERVICES
    assert sum(s.total for s in summaries.values()) == EXPECTED_RECORDS
    assert list(summaries) == sorted(summaries), "summaries must be sorted"


def test_summarize_error_counts():
    records, _ = load_bundled()
    summaries = summarize(records)
    assert summaries["billing"].errors == 7
    assert summaries["worker"].errors == 0
    assert summaries["payment-adapter"].errors == 4
    total_errors = sum(s.errors for s in summaries.values())
    assert total_errors == 17


def test_summarize_error_rate_property():
    records, _ = load_bundled()
    for summary in summarize(records).values():
        assert 0.0 <= summary.error_rate <= 1.0
        assert summary.error_rate == pytest.approx(
            summary.errors / summary.total)


def test_summarize_level_counts():
    summaries = summarize(_records([
        '2025-03-10 09:00:00 INFO service=a msg="x"',
        '2025-03-10 09:00:01 INFO service=a msg="x"',
        '2025-03-10 09:00:02 ERROR service=a msg="x"',
    ]))
    assert summaries["a"].level_counts == {"INFO": 2, "ERROR": 1}


def test_empty_inputs_are_safe():
    assert summarize([]) == {}
    assert rate_by_minute([]) == {}


def test_summary_to_dict_roundtrip():
    records, _ = load_bundled()
    payload = summarize(records)["billing"].to_dict()
    json.dumps(payload)
    assert payload["service"] == "billing"
    assert payload["total"] == 15
    assert payload["errors"] == 7
    assert payload["error_rate"] == pytest.approx(0.4667, abs=1e-4)


def test_threshold_alerts_on_bundled():
    summaries = summarize(load_bundled()[0])
    alerts = threshold_alerts(summaries, DEMO_THRESHOLD, DEMO_MIN_SAMPLES)
    assert {a.service for a in alerts} == EXPECTED_ALERTS
    assert alerts[0].error_rate >= alerts[1].error_rate


def test_threshold_alerts_none_below_threshold():
    summaries = summarize(_records([
        '2025-03-10 09:00:00 INFO service=a msg="x"',
        '2025-03-10 09:00:01 ERROR service=a msg="x"',
    ]))
    assert threshold_alerts(summaries, threshold=0.9) == []


def test_threshold_alerts_min_samples_filter():
    summaries = summarize(_records([
        '2025-03-10 09:00:00 ERROR service=small msg="x"',
        '2025-03-10 09:00:01 ERROR service=big msg="x"',
        '2025-03-10 09:00:02 INFO service=big msg="x"',
        '2025-03-10 09:00:03 INFO service=big msg="x"',
    ]))
    alerts = threshold_alerts(summaries, threshold=0.3, min_samples=3)
    assert [a.service for a in alerts] == ["big"]


def test_threshold_alerts_rejects_bad_args():
    summaries = summarize(load_bundled()[0])
    with pytest.raises(LogError, match="threshold must be in 0..1"):
        threshold_alerts(summaries, threshold=1.5)
    with pytest.raises(LogError, match="threshold must be in 0..1"):
        threshold_alerts(summaries, threshold=-0.1)
    with pytest.raises(LogError, match="min_samples must be >= 1"):
        threshold_alerts(summaries, min_samples=0)


def test_top_offenders_ordering():
    summaries = summarize(load_bundled()[0])
    top = top_offenders(summaries, 3)
    assert [s.service for s in top] == ["billing", "payment-adapter", "auth"]
    assert top[0].errors == 7


def test_top_offenders_ties_break_by_name():
    summaries = summarize(_records([
        '2025-03-10 09:00:00 ERROR service=zebra msg="x"',
        '2025-03-10 09:00:01 ERROR service=aardvark msg="x"',
    ]))
    assert [s.service for s in top_offenders(summaries, 5)] == \
        ["aardvark", "zebra"]


def test_top_offenders_n_and_validation():
    summaries = summarize(load_bundled()[0])
    assert len(top_offenders(summaries, 50)) == len(summaries)
    with pytest.raises(LogError, match="n must be >= 1"):
        top_offenders(summaries, n=0)


def test_rate_by_minute_keys_and_range():
    records, _ = load_bundled()
    rates = rate_by_minute(records)
    assert rates
    assert all(0.0 <= v <= 1.0 for v in rates.values())
    assert list(rates) == sorted(rates)
    assert all(len(key) == 16 for key in rates)  # YYYY-MM-DD HH:MM


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_render_report_sections():
    records, skipped = load_bundled()
    summaries = summarize(records)
    alerts = threshold_alerts(summaries, DEMO_THRESHOLD, DEMO_MIN_SAMPLES)
    top = top_offenders(summaries, 3)
    text = render_report(records, summaries, alerts, top,
                         DEMO_THRESHOLD, DEMO_MIN_SAMPLES, skipped)
    assert "LOG MONITOR REPORT" in text
    assert "Per-service summary:" in text
    assert "Threshold alerts" in text
    assert "Top offenders" in text
    assert str(EXPECTED_RECORDS) in text


def test_render_report_alerts_and_empty_alerts():
    records, _ = load_bundled()
    summaries = summarize(records)
    alerts = threshold_alerts(summaries, DEMO_THRESHOLD, DEMO_MIN_SAMPLES)
    text = render_report(records, summaries, alerts, top_offenders(summaries, 3),
                         DEMO_THRESHOLD, DEMO_MIN_SAMPLES, 0)
    assert "billing" in text and "payment-adapter" in text
    quiet = render_report(records, summaries, [], [], 0.99, 1, 0)
    assert "(none)" in quiet


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK:" in out
    assert "Demo completed successfully." in out
    assert "Top offenders" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_bundled(tmp_path):
    with pytest.raises(LogError, match="bundled sample not found"):
        run_demo(logs=(tmp_path / "nope.log",))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK:" in out


def test_cli_file_analysis(capsys):
    assert main(["--file", str(DATA_DIR / "app.log")]) == 0
    out = capsys.readouterr().out
    assert "LOG MONITOR REPORT" in out
    assert "billing" in out and "Done." in out


def test_cli_file_threshold_and_top(capsys):
    code = main(["--file", str(DATA_DIR / "app.log"),
                 "--threshold", "0.45", "--top", "2", "--quiet"])
    assert code == 0


def test_cli_lenient_skips_bad_lines(tmp_path, capsys):
    path = _write(tmp_path, f"{STRUCTURED}\ngarbage\n")
    assert main(["--file", str(path), "--lenient", "--quiet"]) == 0


def test_cli_strict_bad_line(tmp_path, capsys):
    path = _write(tmp_path, "garbage\n")
    assert main(["--file", str(path)]) == 2
    assert "missing timestamp" in capsys.readouterr().err


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.log")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_json_output(tmp_path, capsys):
    out_json = tmp_path / "report.json"
    code = main(["--file", str(DATA_DIR / "legacy.log"),
                 "--json", str(out_json), "--quiet"])
    assert code == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["records"] == 20
    assert payload["services"][0]["service"] == "cache"
    assert payload["error_rate"] == pytest.approx(0.25)


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_cli_rejects_bad_flags(capsys):
    with pytest.raises(SystemExit):
        main(["--demo", "--threshold", "2.0"])
    with pytest.raises(SystemExit):
        main(["--demo", "--threshold", "high"])
    with pytest.raises(SystemExit):
        main(["--demo", "--top", "0"])
    with pytest.raises(SystemExit):
        main(["--demo", "--min-samples", "0"])


def test_cli_quiet_suppresses_report(capsys):
    assert main(["--file", str(DATA_DIR / "app.log"), "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "LOG MONITOR REPORT" not in out


def test_build_parser_defaults():
    args = build_parser().parse_args(["--demo"])
    assert args.threshold == 0.2
    assert args.top == 5
    assert args.min_samples == 1
    assert not args.lenient


def test_cli_demo_quiet_prints_nothing(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""
