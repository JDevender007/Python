"""Tests for the attendance lab: a timestamp is not a date."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import attendance as module                               # noqa: E402
import main as cli                                        # noqa: E402
from attendance import (                                  # noqa: E402
    GRACE,
    LOG_SEED,
    PEOPLE_SEED,
    SAMPLE_FILE,
    DomainError,
    audit,
    average_late_minutes,
    build_database,
    clock_of,
    day_after,
    day_of,
    divide_half_up,
    insert_log,
    late_minutes,
    late_report,
    legacy_average_late_minutes,
    legacy_bounds,
    legacy_logs_between,
    legacy_sort_stamps,
    logs_between,
    measure,
    minutes_of,
    minutes_of_stamp,
    month_rows,
    orphan_logs,
    parse_day,
    parse_log,
    parse_stamp,
    parsed_month_rows,
    prefix_rows,
    problems,
    range_bounds,
    read_log,
    run_demo,
    sort_stamps,
    split_stamp,
)

CONN = build_database()
MEASURED = measure(CONN)


def verdict(checks, name):
    return dict(checks)[name]


# --------------------------------------------------------------------------- #
# divide_half_up
# --------------------------------------------------------------------------- #
def test_divide_half_up_rounds_a_tie_up():
    assert divide_half_up(5, 2) == 3


def test_divide_half_up_rounds_53_over_2_up():
    assert divide_half_up(53, 2) == 27


def test_divide_half_up_floors_below_the_tie():
    assert divide_half_up(7, 3) == 2


def test_divide_half_up_of_an_exact_division():
    assert divide_half_up(12, 4) == 3


def test_divide_half_up_rounds_a_negative_tie_away_from_zero():
    assert divide_half_up(-5, 2) == -3


def test_divide_half_up_refuses_a_zero_denominator():
    with pytest.raises(DomainError, match="a denominator is positive"):
        divide_half_up(1, 0)


def test_divide_half_up_refuses_a_float_numerator():
    with pytest.raises(DomainError, match="a numerator is a whole number"):
        divide_half_up(1.5, 2)


def test_divide_half_up_refuses_a_bool_denominator():
    with pytest.raises(DomainError, match="a denominator is a whole number"):
        divide_half_up(1, True)


# --------------------------------------------------------------------------- #
# parse_day and parse_stamp
# --------------------------------------------------------------------------- #
def test_parse_day_returns_the_text():
    assert parse_day("2024-03-01") == "2024-03-01"


def test_parse_day_accepts_a_leap_day():
    assert parse_day("2024-02-29") == "2024-02-29"


def test_parse_day_refuses_a_day_that_is_not_on_the_calendar():
    with pytest.raises(DomainError, match="not a day on the calendar"):
        parse_day("2024-02-30")


def test_parse_day_refuses_an_unpadded_day():
    with pytest.raises(DomainError, match="YYYY-MM-DD"):
        parse_day("2024-3-1")


def test_parse_day_refuses_a_blank():
    with pytest.raises(DomainError, match="not blank"):
        parse_day("  ")


def test_parse_day_refuses_a_number():
    with pytest.raises(DomainError, match="is text"):
        parse_day(20240301)


def test_parse_stamp_returns_the_text():
    assert parse_stamp("2024-03-01 09:15") == "2024-03-01 09:15"


@pytest.mark.parametrize("bad", [
    "2024-3-07 09:15", "2024-03-07 9:15", "2024-03-07T09:15",
    "2024-03-07", "2024-03-07 09:15:00", "07/03/2024 09:15",
])
def test_parse_stamp_refuses_a_stamp_it_cannot_read(bad):
    with pytest.raises(DomainError, match="YYYY-MM-DD HH:MM"):
        parse_stamp(bad)


def test_parse_stamp_refuses_the_thirty_first_of_february():
    with pytest.raises(DomainError, match="not a day on the calendar"):
        parse_stamp("2024-02-31 09:15")


def test_parse_stamp_refuses_hour_24():
    with pytest.raises(DomainError, match="not a time on the clock"):
        parse_stamp("2024-03-01 24:00")


def test_parse_stamp_refuses_minute_60():
    with pytest.raises(DomainError, match="not a time on the clock"):
        parse_stamp("2024-03-01 09:60")


def test_parse_stamp_refuses_a_blank():
    with pytest.raises(DomainError, match="not blank"):
        parse_stamp("")


def test_a_stamp_is_not_its_date():
    assert day_of("2024-03-01 09:15") != "2024-03-01 09:15"


def test_split_stamp_returns_a_date_and_a_time():
    assert split_stamp("2024-03-01 09:15") == ("2024-03-01", "09:15")


def test_day_of_drops_the_time():
    assert day_of("2024-03-31 17:40") == "2024-03-31"


def test_clock_of_keeps_only_the_time():
    assert clock_of("2024-03-31 17:40") == "17:40"


def test_split_stamp_refuses_the_legacy_shape():
    with pytest.raises(DomainError, match="YYYY-MM-DD HH:MM"):
        split_stamp("2024/03/01 09:15")


# --------------------------------------------------------------------------- #
# minutes_of
# --------------------------------------------------------------------------- #
def test_minutes_of_midnight_is_zero():
    assert minutes_of("00:00") == 0


def test_minutes_of_the_grace_time_is_555():
    assert minutes_of(GRACE) == 555


def test_minutes_of_0942_is_582():
    assert minutes_of("09:42") == 582


def test_minutes_of_the_last_minute_of_the_day():
    assert minutes_of("23:59") == 1439


def test_minutes_of_refuses_a_single_digit_hour():
    with pytest.raises(DomainError, match="HH:MM"):
        minutes_of("9:42")


def test_minutes_of_refuses_an_impossible_time():
    with pytest.raises(DomainError, match="not a time on the clock"):
        minutes_of("25:00")


def test_minutes_of_stamp_reads_the_clock():
    assert minutes_of_stamp("2024-03-04 09:42") == 582


# --------------------------------------------------------------------------- #
# day_after and the two bounds
# --------------------------------------------------------------------------- #
def test_day_after_steps_over_the_end_of_march():
    assert day_after("2024-03-31") == "2024-04-01"


def test_day_after_steps_over_the_end_of_december():
    assert day_after("2024-12-31") == "2025-01-01"


def test_day_after_steps_over_a_leap_day():
    assert day_after("2024-02-29") == "2024-03-01"


def test_day_after_refuses_a_bad_day():
    with pytest.raises(DomainError, match="not a day on the calendar"):
        day_after("2024-04-31")


def test_range_bounds_end_on_the_next_midnight():
    assert range_bounds("2024-03-01", "2024-03-31") == (
        "2024-03-01 00:00", "2024-04-01 00:00")


def test_range_bounds_of_one_day():
    assert range_bounds("2024-03-31", "2024-03-31") == (
        "2024-03-31 00:00", "2024-04-01 00:00")


def test_range_bounds_refuse_a_reversed_range():
    with pytest.raises(DomainError, match="starts before it ends"):
        range_bounds("2024-03-31", "2024-03-01")


def test_range_bounds_refuse_a_bad_start():
    with pytest.raises(DomainError, match="YYYY-MM-DD"):
        range_bounds("March 1", "2024-03-31")


def test_the_legacy_bounds_are_the_bare_dates():
    assert legacy_bounds("2024-03-01", "2024-03-31") == (
        "2024-03-01", "2024-03-31")


def test_the_legacy_upper_bound_is_below_a_stamp_on_that_day():
    assert "2024-03-31 09:10" > legacy_bounds("2024-03-01", "2024-03-31")[1]


# --------------------------------------------------------------------------- #
# Late minutes
# --------------------------------------------------------------------------- #
def test_late_minutes_of_0942_is_27():
    assert late_minutes("2024-03-04 09:42") == 27


def test_late_minutes_at_the_grace_time_is_zero():
    assert late_minutes("2024-03-04 09:15") == 0


def test_late_minutes_before_the_grace_time_is_zero():
    assert late_minutes("2024-03-04 09:14") == 0


def test_late_minutes_after_midnight_counts_from_midnight():
    assert late_minutes("2024-03-04 00:30") == 0


def test_late_minutes_of_the_last_minute_of_the_day():
    assert late_minutes("2024-03-04 23:59") == 884


def test_late_minutes_with_another_grace():
    assert late_minutes("2024-03-04 09:42", "09:30") == 12


def test_late_minutes_refuse_a_bad_grace():
    with pytest.raises(DomainError, match="HH:MM"):
        late_minutes("2024-03-04 09:42", "9:30")


def test_average_of_53_over_2_is_27():
    assert average_late_minutes(53, 2) == 27


def test_average_of_zero_sessions_is_zero():
    assert average_late_minutes(0, 0) == 0


def test_average_of_zero_minutes_is_zero():
    assert average_late_minutes(0, 3) == 0


def test_average_refuses_a_negative_total():
    with pytest.raises(DomainError, match="not negative"):
        average_late_minutes(-1, 2)


def test_average_refuses_a_negative_session_count():
    with pytest.raises(DomainError, match="not negative"):
        average_late_minutes(10, -1)


def test_average_refuses_a_float_total():
    with pytest.raises(DomainError, match="whole number"):
        average_late_minutes(1.0, 2)


def test_the_legacy_average_rounds_26_5_down():
    assert legacy_average_late_minutes(53, 2) == 26


def test_the_legacy_average_of_zero_sessions_is_zero():
    assert legacy_average_late_minutes(0, 0) == 0


def test_the_two_averages_agree_below_the_tie():
    assert average_late_minutes(52, 2) == 26
    assert legacy_average_late_minutes(52, 2) == 26


# --------------------------------------------------------------------------- #
# Ordering
# --------------------------------------------------------------------------- #
def test_text_order_puts_1000_before_0905():
    pair = ["2024-03-06 9:05", "2024-03-06 10:00"]
    assert legacy_sort_stamps(pair) == ["2024-03-06 10:00",
                                        "2024-03-06 9:05"]


def test_parsed_order_puts_0905_first():
    pair = ["2024-03-06 10:00", "2024-03-06 09:05"]
    assert sort_stamps(pair) == ["2024-03-06 09:05", "2024-03-06 10:00"]


def test_sort_stamps_refuses_a_bad_stamp():
    with pytest.raises(DomainError, match="YYYY-MM-DD HH:MM"):
        sort_stamps(["2024-03-06 9:05"])


def test_legacy_sort_accepts_anything():
    assert legacy_sort_stamps(["b", "a"]) == ["a", "b"]


def test_sort_stamps_does_not_mutate_its_input():
    held = ["2024-03-06 10:00", "2024-03-06 09:05"]
    sort_stamps(held)
    assert held == ["2024-03-06 10:00", "2024-03-06 09:05"]


# --------------------------------------------------------------------------- #
# The database
# --------------------------------------------------------------------------- #
def test_build_database_counts_ten_check_ins():
    fresh = build_database()
    try:
        assert fresh.execute("SELECT COUNT(*) FROM logs").fetchone()[0] == 10
    finally:
        fresh.close()


def test_build_database_has_three_people():
    fresh = build_database()
    try:
        assert fresh.execute("SELECT COUNT(*) FROM people").fetchone()[0] == 3
    finally:
        fresh.close()


def test_build_database_enforces_foreign_keys():
    fresh = build_database()
    try:
        assert fresh.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        fresh.close()


def test_build_database_refuses_an_unknown_person_code():
    with pytest.raises(DomainError, match="no person with the code"):
        build_database(logs=(("STU999", "2024-03-01 09:05"),))


def test_build_database_refuses_a_duplicate_check_in():
    with pytest.raises(DomainError, match="already has a check-in"):
        build_database(logs=(("STU001", "2024-03-01 09:05"),
                             ("STU001", "2024-03-01 09:05")))


def test_insert_log_refuses_a_bad_stamp():
    fresh = build_database()
    try:
        with pytest.raises(DomainError, match="YYYY-MM-DD HH:MM"):
            insert_log(fresh, "STU001", "2024-3-02 09:00")
    finally:
        fresh.close()


def test_insert_log_returns_an_id():
    fresh = build_database()
    try:
        assert insert_log(fresh, "STU002", "2024-03-07 09:00") == 11
    finally:
        fresh.close()


def test_logs_between_reads_all_ten():
    assert len(logs_between(CONN, "2024-03-01", "2024-03-31")) == 10


def test_the_legacy_range_reads_seven():
    assert len(legacy_logs_between(CONN, "2024-03-01", "2024-03-31")) == 7


def test_the_correct_range_keeps_the_last_day():
    assert len(logs_between(CONN, "2024-03-31", "2024-03-31")) == 3


def test_the_legacy_range_loses_the_last_day():
    assert len(legacy_logs_between(CONN, "2024-03-31", "2024-03-31")) == 0


def test_the_same_bug_hits_a_one_day_range_in_the_middle():
    assert len(logs_between(CONN, "2024-03-04", "2024-03-04")) == 2
    assert len(legacy_logs_between(CONN, "2024-03-04", "2024-03-04")) == 0


def test_logs_between_is_ordered_by_stamp():
    rows = logs_between(CONN, "2024-03-01", "2024-03-31")
    assert [row[2] for row in rows] == sorted(row[2] for row in rows)


def test_the_report_has_three_people_in_code_order():
    assert [row["code"] for row in late_report(
        CONN, "2024-03-01", "2024-03-31")] == ["STU001", "STU002", "STU003"]


def test_the_first_person_has_four_days_and_two_late_days():
    row = late_report(CONN, "2024-03-01", "2024-03-31")[0]
    assert row["days"] == 4
    assert row["late_days"] == 2


def test_the_first_person_has_53_late_minutes_and_a_mean_of_27():
    row = late_report(CONN, "2024-03-01", "2024-03-31")[0]
    assert row["late_minutes"] == 53
    assert row["average"] == 27
    assert row["legacy_average"] == 26


def test_the_whole_report_holds_83_late_minutes():
    report = late_report(CONN, "2024-03-01", "2024-03-31")
    assert sum(row["late_minutes"] for row in report) == 83


def test_a_range_with_no_check_ins_is_an_empty_report():
    assert late_report(CONN, "2024-04-01", "2024-04-30") == []


def test_no_check_in_is_an_orphan():
    assert orphan_logs(CONN) == 0


def test_a_deleted_person_takes_their_check_ins_with_them():
    fresh = build_database()
    try:
        fresh.execute("DELETE FROM people WHERE code = 'STU001'")
        fresh.commit()
        assert fresh.execute("SELECT COUNT(*) FROM logs").fetchone()[0] == 6
    finally:
        fresh.close()


def test_month_rows_asks_for_the_real_month():
    rows = month_rows(CONN, "2024-03")
    assert len(rows) == 10
    assert rows[0] == ("STU001", "2024-03-01 09:05")


def test_month_rows_refuses_a_bad_month():
    with pytest.raises(DomainError, match="YYYY-MM"):
        month_rows(CONN, "2024-3")


def test_month_rows_refuses_month_13():
    with pytest.raises(DomainError, match="not a month"):
        month_rows(CONN, "2024-13")


def test_a_prefix_hides_the_unpadded_row():
    mixed = ["2024-03-01 09:15", "2024-3-07 09:15"]
    assert prefix_rows(mixed, "2024-03") == ["2024-03-01 09:15"]


def test_a_parsed_month_refuses_the_unpadded_row():
    mixed = ["2024-03-01 09:15", "2024-3-07 09:15"]
    with pytest.raises(DomainError, match="YYYY-MM-DD HH:MM"):
        parsed_month_rows(mixed, "2024-03")


# --------------------------------------------------------------------------- #
# Reading the bundled CSV
# --------------------------------------------------------------------------- #
def test_the_bundled_csv_reads_ten_check_ins():
    people, logs = read_log()
    assert len(logs) == 10


def test_the_bundled_csv_reads_three_people():
    people, logs = read_log()
    assert people == PEOPLE_SEED


def test_the_bundled_csv_matches_the_built_in_seed():
    people, logs = read_log()
    assert people == PEOPLE_SEED
    assert logs == LOG_SEED


def test_the_bundled_file_exists():
    assert SAMPLE_FILE.is_file()


def test_read_log_refuses_a_missing_file(tmp_path):
    with pytest.raises(DomainError, match="file not found"):
        read_log(tmp_path / "absent.csv")


def test_parse_log_refuses_a_short_row():
    with pytest.raises(DomainError, match="four fields"):
        parse_log("STU001,Aarav\n")


def test_parse_log_refuses_a_bad_stamp_with_its_line():
    with pytest.raises(DomainError, match="line 1"):
        parse_log("STU001,Aarav,Batch A,2024-3-01 09:00\n")


def test_parse_log_refuses_two_names_for_one_code():
    text = ("STU001,Aarav,Batch A,2024-03-01 09:00\n"
            "STU001,Someone,Batch A,2024-03-02 09:00\n")
    with pytest.raises(DomainError, match="already named"):
        parse_log(text)


def test_parse_log_refuses_a_repeated_check_in():
    text = ("STU001,Aarav,Batch A,2024-03-01 09:00\n"
            "STU001,Aarav,Batch A,2024-03-01 09:00\n")
    with pytest.raises(DomainError, match="checks in twice"):
        parse_log(text)


def test_parse_log_refuses_a_blank_document():
    with pytest.raises(DomainError, match="at least one check-in"):
        parse_log("# only a comment\n")


def test_parse_log_ignores_comments_and_blank_lines():
    text = ("# a comment\n\nSTU001,Aarav,Batch A,2024-03-01 09:00\n")
    people, logs = parse_log(text)
    assert people == (("STU001", "Aarav", "Batch A"),)
    assert logs == (("STU001", "2024-03-01 09:00"),)


# --------------------------------------------------------------------------- #
# Measurements and audit
# --------------------------------------------------------------------------- #
def test_the_measurement_holds_the_two_range_counts():
    assert MEASURED["rows"] == 10
    assert MEASURED["legacy_rows"] == 7


def test_the_measurement_holds_the_last_day_counts():
    assert MEASURED["last_day_correct"] == 3
    assert MEASURED["last_day_legacy"] == 0


def test_the_measurement_holds_the_average_pair():
    assert MEASURED["average_53_2"] == 27
    assert MEASURED["legacy_average_53_2"] == 26


def test_the_measurement_holds_the_total_late_minutes():
    assert MEASURED["late_total"] == 83
    assert MEASURED["late_days"] == 4


def test_the_measurement_holds_the_month_prefix_pair():
    assert MEASURED["prefix_month"] == 1
    assert MEASURED["parsed_month"] == 0


def test_every_audit_check_passes_on_the_bundled_data():
    checks = audit(MEASURED, make_database=build_database)
    assert len(checks) == 12
    assert problems(checks) == []


def test_the_audit_names_its_checks():
    names = [name for name, _ in audit(MEASURED)]
    assert names[0] == "a stamp keeps its time"
    assert names[-1] == "a rebuilt database counts the same"


def test_a_corrupted_range_count_fails_its_check():
    broken = dict(MEASURED)
    broken["legacy_rows"] = 8
    assert verdict(audit(broken), "a text range drops the last day") is False


def test_a_corrupted_last_day_count_fails_its_check():
    broken = dict(MEASURED)
    broken["last_day_legacy"] = 3
    assert verdict(audit(broken),
                   "the last day is what the text range loses") is False


def test_a_corrupted_average_fails_its_check():
    broken = dict(MEASURED)
    broken["legacy_average_53_2"] = 27
    assert verdict(audit(broken), "a late average is divided half up") is False


def test_a_corrupted_report_total_fails_its_check():
    broken = dict(MEASURED)
    broken["late_total"] = 84
    assert verdict(audit(broken), "the report adds up to the stamps") is False


def test_a_missing_measurement_fails_instead_of_raising():
    assert verdict(audit({}), "a stamp keeps its time") is False


def test_a_factory_with_nine_rows_fails_the_count_check():
    short = lambda: build_database(logs=LOG_SEED[:-1])        # noqa: E731
    assert verdict(audit(MEASURED, make_database=short),
                   "every check in belongs to a person") is False


def test_a_factory_with_an_extra_row_fails_the_rebuild_check():
    extra = LOG_SEED + (("STU001", "2024-03-07 09:00"),)
    factory = lambda: build_database(logs=extra)               # noqa: E731
    assert verdict(audit(MEASURED, make_database=factory),
                   "a rebuilt database counts the same") is False


def test_a_factory_that_raises_fails_the_check():
    def broken():
        raise RuntimeError("no database for you")
    assert verdict(audit(MEASURED, make_database=broken),
                   "every check in belongs to a person") is False


# --------------------------------------------------------------------------- #
# The demo and the CLI
# --------------------------------------------------------------------------- #
def test_the_demo_returns_zero():
    assert run_demo() == 0


def test_the_demo_ends_with_the_two_required_lines(capsys):
    run_demo()
    lines = capsys.readouterr().out.rstrip("\n").split("\n")
    assert lines[-1] == "Demo completed successfully."
    assert lines[-2].startswith("Cross-checks OK: ")


def test_the_demo_prints_twelve_verdicts(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert out.count("  PASS  ") == 12


def test_the_demo_prints_the_legacy_range(capsys):
    run_demo()
    assert "WHERE l.stamp BETWEEN ? AND ?" in capsys.readouterr().out


def test_the_demo_is_byte_identical_across_runs(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    second = capsys.readouterr().out
    assert first == second


def test_the_demo_quiet_prints_nothing(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_the_cli_prints_the_report(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "10 check-ins from 2024-03-01 to 2024-03-31" in out
    assert "STU001" in out


def test_the_cli_reports_the_legacy_count(capsys):
    cli.main([])
    assert "the legacy BETWEEN reads 7 of 10 rows" in capsys.readouterr().out


def test_the_cli_writes_json(tmp_path, capsys):
    destination = tmp_path / "report.json"
    assert cli.main(["--json", str(destination)]) == 0
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["check_ins"] == 10
    assert payload["legacy_check_ins"] == 7
    assert payload["report"][0]["average"] == 27


def test_the_cli_audit_returns_zero(capsys):
    assert cli.main(["--audit"]) == 0
    assert "12/12" not in capsys.readouterr().out


def test_the_cli_prints_twelve_verdicts_with_audit(capsys):
    cli.main(["--audit"])
    assert capsys.readouterr().out.count("PASS") == 12


def test_the_cli_refuses_a_missing_file(tmp_path, capsys):
    assert cli.main(["--file", str(tmp_path / "absent.csv")]) == 2
    assert "error: file not found" in capsys.readouterr().err


def test_the_cli_refuses_a_bad_range(capsys):
    assert cli.main(["--from", "2024-03-31", "--to", "2024-03-01"]) == 2
    assert "error: a range starts before it ends" in capsys.readouterr().err


def test_the_cli_refuses_a_bad_day(capsys):
    assert cli.main(["--from", "March"]) == 2
    assert "error: a day is written" in capsys.readouterr().err


def test_the_cli_refuses_a_short_row_in_a_file(tmp_path, capsys):
    source = tmp_path / "short.csv"
    source.write_text("STU001,Aarav\n", encoding="utf-8")
    assert cli.main(["--file", str(source)]) == 2
    assert "four fields" in capsys.readouterr().err


def test_the_cli_quiet_writes_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_the_module_is_ascii():
    source = Path(module.__file__).read_bytes()
    assert all(byte < 128 for byte in source)
