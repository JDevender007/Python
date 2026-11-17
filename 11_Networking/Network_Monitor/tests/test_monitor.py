"""Tests for the uptime lab: intervals, basis points, MTTR and MTBF."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import main as cli  # noqa: E402
import monitor  # noqa: E402
from monitor import (  # noqa: E402
    LEGACY_INTERVALS,
    LEGACY_UPTIME,
    Interval,
    MonitorError,
    Transition,
    Window,
    audit,
    build_intervals,
    divide_half_up,
    format_bp,
    legacy_intervals,
    legacy_uptime_bp,
    load_changes,
    load_window,
    longest_outage_s,
    measure,
    mtbf_s,
    mttr_s,
    render_intervals,
    report,
    run_demo,
    state_of,
    totals,
    uptime_bp,
    uptime_over_covered_bp,
)

WINDOW = Window(0, 10_000)


def rows(*pairs: tuple[int, str]) -> list[Transition]:
    return [
        Transition(index + 1, at, state, f"note {index + 1}")
        for index, (at, state) in enumerate(pairs)
    ]


SEED = rows((0, "up"), (100, "down"), (8800, "up"), (9000, "down"), (9400, "up"), (9700, "down"))


# --------------------------------------------------------------------------- #
# arithmetic and formatting
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "top,bottom,expected",
    [(9400, 3, 3133), (600, 3, 200), (600 * 10_000, 10_000, 600), (5, 2, 3), (1, 3, 0),
     (2, 3, 1), (-5, 2, -3), (0, 7, 0)],
)
def test_divide_half_up(top, bottom, expected):
    assert divide_half_up(top, bottom) == expected


@pytest.mark.parametrize("bottom", [0, -1])
def test_divide_half_up_refuses_bad_denominators(bottom):
    with pytest.raises(MonitorError, match="denominator must be positive"):
        divide_half_up(1, bottom)


@pytest.mark.parametrize("bad", [True, 1.5, "10"])
def test_divide_half_up_refuses_non_integers(bad):
    with pytest.raises(MonitorError, match="must be an integer"):
        divide_half_up(bad, 2)


@pytest.mark.parametrize(
    "bp,text", [(600, "6.00"), (5000, "50.00"), (619, "6.19"), (0, "0.00"),
                (10_000, "100.00"), (5, "0.05"), (-5, "-0.05")]
)
def test_format_bp(bp, text):
    assert format_bp(bp) == text


def test_format_bp_refuses_a_non_integer():
    with pytest.raises(MonitorError, match="must be an integer"):
        format_bp(6.0)


# --------------------------------------------------------------------------- #
# states and windows
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,expected", [("up", "up"), ("DOWN", "down"), (" up ", "up")])
def test_state_of_normalises(text, expected):
    assert state_of(text) == expected


@pytest.mark.parametrize("text", ["", "  ", "ok", "UP?", "degraded"])
def test_state_of_refuses_anything_else(text):
    with pytest.raises(MonitorError):
        state_of(text)


def test_state_of_refuses_non_text():
    with pytest.raises(MonitorError, match="must be text"):
        state_of(None)


def test_window_seconds_is_the_difference():
    assert WINDOW.seconds == 10_000


def test_load_window_reads_the_bundled_file():
    window = load_window()
    assert (window.start_s, window.end_s) == (0, 10_000)
    assert window.seconds == 10_000


def test_load_window_refuses_a_missing_file(tmp_path):
    with pytest.raises(MonitorError, match="file not found"):
        load_window(tmp_path / "nope.csv")


def test_load_window_refuses_two_rows(tmp_path):
    path = tmp_path / "window.csv"
    path.write_text("start_s,end_s\n0,10\n0,20\n", encoding="utf-8")
    with pytest.raises(MonitorError, match="exactly one row"):
        load_window(path)


@pytest.mark.parametrize("body", ["0,0\n", "10,5\n", "-1,5\n"])
def test_load_window_refuses_a_bad_range(tmp_path, body):
    path = tmp_path / "window.csv"
    path.write_text("start_s,end_s\n" + body, encoding="utf-8")
    with pytest.raises(MonitorError):
        load_window(path)


def test_load_window_refuses_a_missing_column(tmp_path):
    path = tmp_path / "window.csv"
    path.write_text("start_s\n0\n", encoding="utf-8")
    with pytest.raises(MonitorError, match="missing column"):
        load_window(path)


# --------------------------------------------------------------------------- #
# the transition log
# --------------------------------------------------------------------------- #
def test_load_changes_reads_the_bundled_log():
    changes = load_changes()
    assert len(changes) == 6
    assert [change.state for change in changes] == [
        "up", "down", "up", "down", "up", "down"
    ]
    assert changes[2].at_s == 8800
    assert changes[5].note == "certificate renewal failed"


def test_load_changes_refuses_a_missing_file(tmp_path):
    with pytest.raises(MonitorError, match="file not found"):
        load_changes(tmp_path / "nope.csv")


def test_load_changes_refuses_an_empty_log(tmp_path):
    path = tmp_path / "changes.csv"
    path.write_text("seq,changed_at_s,state,note\n", encoding="utf-8")
    with pytest.raises(MonitorError, match="holds no transitions"):
        load_changes(path)


def test_load_changes_refuses_an_unknown_state(tmp_path):
    path = tmp_path / "changes.csv"
    path.write_text("seq,changed_at_s,state,note\n1,0,up,a\n2,5,flapping,b\n", encoding="utf-8")
    with pytest.raises(MonitorError, match="state must be one of"):
        load_changes(path)


def test_load_changes_refuses_a_duplicate_seq(tmp_path):
    path = tmp_path / "changes.csv"
    path.write_text("seq,changed_at_s,state,note\n1,0,up,a\n1,5,down,b\n", encoding="utf-8")
    with pytest.raises(MonitorError, match="seq values must be unique"):
        load_changes(path)


def test_load_changes_refuses_rows_out_of_order(tmp_path):
    path = tmp_path / "changes.csv"
    path.write_text("seq,changed_at_s,state,note\n1,50,up,a\n2,5,down,b\n", encoding="utf-8")
    with pytest.raises(MonitorError, match="changed_at_s order"):
        load_changes(path)


def test_load_changes_refuses_a_negative_time(tmp_path):
    path = tmp_path / "changes.csv"
    path.write_text("seq,changed_at_s,state,note\n1,-5,up,a\n", encoding="utf-8")
    with pytest.raises(MonitorError, match="must not be negative"):
        load_changes(path)


def test_load_changes_refuses_a_non_numeric_time(tmp_path):
    path = tmp_path / "changes.csv"
    path.write_text("seq,changed_at_s,state,note\n1,soon,up,a\n", encoding="utf-8")
    with pytest.raises(MonitorError, match="whole number"):
        load_changes(path)


# --------------------------------------------------------------------------- #
# intervals
# --------------------------------------------------------------------------- #
def test_build_intervals_tiles_the_window():
    intervals = build_intervals(WINDOW, SEED)
    assert [(i.state, i.start_s, i.end_s) for i in intervals] == [
        ("up", 0, 100),
        ("down", 100, 8800),
        ("up", 8800, 9000),
        ("down", 9000, 9400),
        ("up", 9400, 9700),
        ("down", 9700, 10_000),
    ]
    assert sum(interval.seconds for interval in intervals) == 10_000


def test_the_final_interval_ends_at_the_window_end():
    intervals = build_intervals(WINDOW, SEED)
    assert intervals[-1].end_s == WINDOW.end_s
    assert intervals[-1].seconds == 300


def test_interval_seconds():
    assert Interval("up", 10, 40).seconds == 30


def test_build_intervals_refuses_an_empty_log():
    with pytest.raises(MonitorError, match="at least one row"):
        build_intervals(WINDOW, [])


def test_build_intervals_refuses_a_first_transition_after_the_start():
    with pytest.raises(MonitorError, match="not at the window start"):
        build_intervals(WINDOW, rows((1, "up")))


def test_build_intervals_refuses_a_repeated_state():
    with pytest.raises(MonitorError, match="must alternate"):
        build_intervals(WINDOW, rows((0, "up"), (5, "up")))


def test_build_intervals_refuses_a_transition_at_the_window_end():
    with pytest.raises(MonitorError, match="outside the window"):
        build_intervals(WINDOW, rows((0, "up"), (10_000, "down")))


def test_build_intervals_refuses_a_transition_before_the_window():
    window = Window(100, 200)
    with pytest.raises(MonitorError, match="outside the window"):
        build_intervals(window, rows((100, "up"), (50, "down")))


def test_build_intervals_refuses_two_transitions_at_the_same_second():
    with pytest.raises(MonitorError, match="does not follow"):
        build_intervals(WINDOW, rows((0, "up"), (0, "down")))


def test_build_intervals_refuses_a_non_positive_window():
    with pytest.raises(MonitorError, match="must be greater than"):
        build_intervals(Window(10, 10), rows((10, "up")))


def test_a_single_transition_covers_the_whole_window():
    intervals = build_intervals(WINDOW, rows((0, "down")))
    assert [(i.state, i.seconds) for i in intervals] == [("down", 10_000)]


def test_totals_sums_by_state():
    assert totals(build_intervals(WINDOW, SEED)) == {"up": 600, "down": 9400}


def test_totals_of_no_intervals_is_zero():
    assert totals([]) == {"up": 0, "down": 0}


# --------------------------------------------------------------------------- #
# availability
# --------------------------------------------------------------------------- #
def test_uptime_bp_is_six_percent():
    assert uptime_bp(build_intervals(WINDOW, SEED), WINDOW) == 600


def test_uptime_bp_of_an_all_up_window_is_ten_thousand():
    assert uptime_bp(build_intervals(WINDOW, rows((0, "up"))), WINDOW) == 10_000


def test_uptime_bp_of_an_all_down_window_is_zero():
    assert uptime_bp(build_intervals(WINDOW, rows((0, "down"))), WINDOW) == 0


def test_uptime_bp_rounds_half_up_at_the_boundary():
    window = Window(0, 8)
    intervals = [Interval("up", 0, 1), Interval("down", 1, 8)]
    assert uptime_bp(intervals, window) == 1250


def test_uptime_over_covered_bp_ignores_the_uncovered_span():
    assert uptime_over_covered_bp(legacy_intervals(WINDOW, SEED)) == 619


def test_uptime_over_covered_bp_refuses_an_empty_span():
    with pytest.raises(MonitorError, match="no interval covers any time"):
        uptime_over_covered_bp([])


def test_legacy_uptime_counts_rows():
    assert legacy_uptime_bp(SEED) == 5000


def test_legacy_uptime_refuses_an_empty_log():
    with pytest.raises(MonitorError, match="at least one row"):
        legacy_uptime_bp([])


def test_legacy_intervals_drop_the_final_interval():
    covered = legacy_intervals(WINDOW, SEED)
    assert len(covered) == 5
    assert sum(interval.seconds for interval in covered) == 9700


def test_legacy_intervals_of_a_single_row_is_empty():
    assert legacy_intervals(WINDOW, rows((0, "up"))) == []


def test_mttr_divides_downtime_by_outages():
    assert mttr_s(build_intervals(WINDOW, SEED)) == 3133


def test_mttr_is_zero_without_outages():
    assert mttr_s(build_intervals(WINDOW, rows((0, "up")))) == 0


def test_mtbf_divides_uptime_by_recoveries():
    assert mtbf_s(build_intervals(WINDOW, SEED)) == 200


def test_mtbf_is_zero_without_recoveries():
    assert mtbf_s(build_intervals(WINDOW, rows((0, "down")))) == 0


def test_longest_outage():
    assert longest_outage_s(build_intervals(WINDOW, SEED)) == 8700
    assert longest_outage_s(build_intervals(WINDOW, rows((0, "up")))) == 0


def test_the_row_ratio_overstates_by_44_points():
    measured = measure()
    assert measured["legacy_bp"] - measured["uptime_bp"] == 4400


# --------------------------------------------------------------------------- #
# measure and report
# --------------------------------------------------------------------------- #
def test_measure_pins_the_seed():
    measured = measure()
    assert measured["totals"] == {"up": 600, "down": 9400}
    assert measured["uptime_bp"] == 600
    assert measured["legacy_bp"] == 5000
    assert measured["legacy_uptime_bp"] == 619
    assert measured["legacy_covered_s"] == 9700
    assert measured["mttr_s"] == 3133
    assert measured["mtbf_s"] == 200
    assert measured["outages"] == 3
    assert measured["up_rows"] == 3


def test_measure_reads_the_window_beside_the_changes(tmp_path):
    (tmp_path / "window.csv").write_text("start_s,end_s\n0,100\n", encoding="utf-8")
    (tmp_path / "changes.csv").write_text(
        "seq,changed_at_s,state,note\n1,0,up,a\n2,50,down,b\n", encoding="utf-8"
    )
    measured = measure(tmp_path / "changes.csv")
    assert measured["totals"] == {"up": 50, "down": 50}
    assert measured["uptime_bp"] == 5000


def test_measure_accepts_an_explicit_window_path(tmp_path):
    (tmp_path / "changes.csv").write_text(
        "seq,changed_at_s,state,note\n1,0,up,a\n", encoding="utf-8"
    )
    other = tmp_path / "other_window.csv"
    other.write_text("start_s,end_s\n0,10\n", encoding="utf-8")
    measured = measure(tmp_path / "changes.csv", window_path=other)
    assert measured["totals"] == {"up": 10, "down": 0}
    assert measured["uptime_bp"] == 10_000


def test_report_is_json_safe():
    payload = report(measure())
    text = json.dumps(payload, sort_keys=True)
    assert "Window(" not in text
    assert payload["window_s"] == 10_000
    assert payload["up_s"] == 600
    assert payload["down_s"] == 9400
    assert payload["uptime_percent"] == "6.00"
    assert payload["legacy_percent"] == "50.00"
    assert payload["legacy_uptime_percent"] == "6.19"
    assert payload["mttr_s"] == 3133
    assert payload["intervals"][-1] == {"state": "down", "start_s": 9700, "end_s": 10_000}


def test_render_intervals_shows_every_row():
    rendered = render_intervals(measure())
    assert "up             0      100       100     1.00%" in rendered
    assert "TOTAL" in rendered
    assert "up 600 s, down 9400 s, 3 outages" in rendered


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def test_audit_passes_every_check():
    results = audit(measure())
    assert len(results) == 18
    assert all(ok for _, ok in results)


def test_audit_names_are_unique():
    names = [name for name, _ in audit(measure())]
    assert len(names) == len(set(names))


def test_audit_negative_control_legacy_reader_flips_the_tiling():
    results = dict(audit(measure(), read_intervals=legacy_intervals))
    assert results["intervals_tile_the_window_exactly"] is False
    assert results["intervals_alternate_and_start_at_the_window"] is True
    assert results["rebuild_is_deterministic"] is False


def test_audit_negative_control_reader_that_raises():
    def broken(window, changes):
        raise MonitorError("boom")

    results = dict(audit(measure(), read_intervals=broken))
    assert results["intervals_tile_the_window_exactly"] is False
    assert results["rebuild_is_deterministic"] is False


def test_audit_negative_control_reader_that_stretches_the_last_interval():
    def stretched(window, changes):
        intervals = build_intervals(window, changes)
        last = intervals[-1]
        return intervals[:-1] + [Interval(last.state, last.start_s, last.end_s + 1)]

    results = dict(audit(measure(), read_intervals=stretched))
    assert results["intervals_tile_the_window_exactly"] is False


def test_audit_detects_a_tampered_up_seconds():
    measured = measure()
    measured["totals"] = {"up": 700, "down": 9300}
    results = dict(audit(measured))
    assert results["up_seconds_match_an_independent_loop"] is False
    assert results["up_seconds_are_pinned"] is False


def test_audit_detects_a_tampered_legacy_percentage():
    measured = measure()
    measured["legacy_bp"] = 600
    results = dict(audit(measured))
    assert results["the_legacy_report_counts_rows"] is False
    assert results["the_row_count_overstates_availability_by_44_points"] is False


def test_audit_detects_a_tampered_covered_span():
    measured = measure()
    measured["legacy_covered_s"] = 10_000
    assert dict(audit(measured))["the_pairwise_loop_drops_the_final_interval"] is False


def test_audit_detects_a_tampered_mttr():
    measured = measure()
    measured["mttr_s"] = 3134
    assert dict(audit(measured))["mttr_divides_downtime_by_outages"] is False


def test_audit_detects_a_tampered_outage_count():
    measured = measure()
    measured["outages"] = 2
    results = dict(audit(measured))
    assert results["there_are_three_outages_and_one_is_the_longest"] is False
    assert results["mttr_divides_downtime_by_outages"] is False


# --------------------------------------------------------------------------- #
# demo and CLI
# --------------------------------------------------------------------------- #
def test_run_demo_returns_zero_and_ends_with_the_contract(capsys):
    assert run_demo() == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1] == "Demo completed successfully."
    assert lines[-2].startswith("Cross-checks OK: ")


def test_run_demo_is_byte_identical(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    second = capsys.readouterr().out
    assert first == second


def test_demo_prints_the_pinned_numbers(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "3 of 6 rows say 'up', so the legacy report prints 50.00%" in out
    assert "which is 6.00%" in out
    assert "losing the final 300 s" in out
    assert "reports 6.19% over what it did cover" in out
    assert "MTTR 3133 s" in out
    assert "18/18 checks pass" in out
    assert "FAIL" not in out


def test_demo_output_is_ascii_and_quiet_on_stderr(capsys):
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        run_demo()
    assert err.getvalue() == ""


def test_the_legacy_snippets_are_kept_as_text():
    assert "round(100" in LEGACY_UPTIME
    assert "zip(rows, rows[1:])" in LEGACY_INTERVALS


def test_cli_demo_exits_zero():
    assert cli.main(["--demo"]) == 0


def test_cli_demo_quiet_prints_nothing(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_json_writes_a_report(tmp_path):
    target = tmp_path / "report.json"
    assert cli.main(["--json", str(target)]) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["uptime_bp"] == 600
    assert payload["legacy_bp"] == 5000


def test_cli_json_creates_the_parent_folder(tmp_path):
    target = tmp_path / "nested" / "report.json"
    assert cli.main(["--json", str(target)]) == 0
    assert target.is_file()


def test_cli_audit_passes():
    assert cli.main(["--audit"]) == 0


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "no/such/changes.csv"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_repeated_state_exits_two(tmp_path, capsys):
    folder = tmp_path / "seeds"
    folder.mkdir()
    (folder / "window.csv").write_text("start_s,end_s\n0,100\n", encoding="utf-8")
    (folder / "changes.csv").write_text(
        "seq,changed_at_s,state,note\n1,0,up,a\n2,50,up,b\n", encoding="utf-8"
    )
    assert cli.main(["--file", str(folder / "changes.csv")]) == 2
    assert "alternate" in capsys.readouterr().err


def test_cli_prints_both_percentages(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "uptime 6.00% (600 s up, 9400 s down), legacy 50.00%" in out


def test_cli_quiet_json_still_writes(tmp_path):
    target = tmp_path / "quiet.json"
    assert cli.main(["--quiet", "--json", str(target)]) == 0
    assert target.is_file()


def test_module_audit_is_exposed():
    assert monitor.audit is audit
