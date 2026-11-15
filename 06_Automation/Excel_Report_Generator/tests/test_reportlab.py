"""Tests for Excel_Report_Generator: a mean without its denominator is not a
number, and money that is a float is wrong before it is rounded."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                            # noqa: E402
import reportlab as module                                    # noqa: E402
from reportlab import (                                       # noqa: E402
    COUNT,
    GAP_LIMIT,
    KINDS,
    LEGACY_SUMMARY,
    LEGACY_TYPES,
    MONEY,
    SALES_FILE,
    Column,
    Excluded,
    Group,
    ReportError,
    Stat,
    Table,
    audit,
    build_report,
    divide_half_up,
    group_rows,
    kind_of,
    money,
    parse_count,
    parse_money,
    parse_table,
    profile,
    problems,
    read_table,
    run_demo,
    split_fields,
)

HEADER = "order_id,region,units,unit_price,shipping\n"
ROWS = ("A-1,North,2,10.00,1.50\n"
        "A-2,North,1,5.25,\n"
        "A-3,South,,4.00,2.00\n")


def a_file(folder: Path, text: str, name: str = "sales.csv") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(text.encode("utf-8"))
    return path


def bundled():
    return read_table()


def a_report(**changes):
    return replace(build_report(bundled()), **changes)


def with_column(report, name, **changes):
    columns = tuple(replace(column, **changes) if column.name == name
                    else column for column in report.columns)
    return replace(report, columns=columns)


def small():
    return parse_table(HEADER + ROWS)


# --------------------------------------------------------------------------- #
# Money, in cents
# --------------------------------------------------------------------------- #
def test_a_price_becomes_cents():
    assert parse_money("12.34") == 1234


def test_a_negative_price_becomes_negative_cents():
    assert parse_money("-0.05") == -5


def test_a_zero_price_is_zero_cents():
    assert parse_money("0.00") == 0


def test_a_price_drops_surrounding_space():
    assert parse_money(" 7.50 ") == 750


def test_one_decimal_is_refused_rather_than_rounded():
    with pytest.raises(ReportError, match="needs two decimals"):
        parse_money("12.3")


def test_three_decimals_are_refused():
    with pytest.raises(ReportError, match="needs two decimals"):
        parse_money("12.345")


def test_a_whole_number_without_a_dot_is_refused():
    with pytest.raises(ReportError, match="needs two decimals"):
        parse_money("12")


def test_a_thousands_separator_is_refused():
    with pytest.raises(ReportError, match="needs two decimals"):
        parse_money("1,234.00")


def test_a_price_that_is_not_text_is_refused():
    with pytest.raises(ReportError, match="must be text"):
        parse_money(12.34)


def test_money_keeps_the_cents_visible():
    assert money(319) == "3.19" and money(5) == "0.05" and money(0) == "0.00"


def test_money_keeps_the_sign():
    assert money(-5) == "-0.05"


def test_money_refuses_a_float():
    with pytest.raises(ReportError, match="whole cents"):
        money(3.19)


def test_money_refuses_a_bool():
    with pytest.raises(ReportError, match="whole cents"):
        money(True)


def test_a_count_parses():
    assert parse_count("12") == 12


def test_a_negative_count_parses():
    assert parse_count("-3") == -3


def test_a_decimal_count_is_refused():
    with pytest.raises(ReportError, match="needs whole numbers"):
        parse_count("12.0")


def test_a_count_that_is_not_text_is_refused():
    with pytest.raises(ReportError, match="must be text"):
        parse_count(12)


def test_half_a_cent_rounds_up():
    assert divide_half_up(2548, 8) == 319


def test_three_half_cents_round_up():
    assert divide_half_up(301, 2) == 151


def test_round_does_not_agree_with_half_up_on_a_tie():
    """The defect, executable: Python rounds half to even."""
    assert round(318.5) == 318
    assert divide_half_up(2548, 8) == 319


def test_a_third_rounds_down():
    assert divide_half_up(1, 3) == 0


def test_two_thirds_round_up():
    assert divide_half_up(2, 3) == 1


def test_an_exact_division_is_unchanged():
    assert divide_half_up(1000, 4) == 250


def test_a_negative_tie_rounds_away_from_zero():
    assert divide_half_up(-3, 2) == -2


def test_a_negative_below_half_rounds_towards_zero():
    assert divide_half_up(-1, 3) == 0


def test_a_mean_of_nothing_is_refused():
    with pytest.raises(ReportError, match="needs something to divide by"):
        divide_half_up(10, 0)


def test_a_float_total_is_refused():
    with pytest.raises(ReportError, match="whole number of cents"):
        divide_half_up(10.5, 2)


def test_the_legacy_float_sum_is_pinned():
    assert 0.1 + 0.2 == 0.30000000000000004
    assert parse_money("0.10") + parse_money("0.20") == 30


# --------------------------------------------------------------------------- #
# Reading a CSV
# --------------------------------------------------------------------------- #
def test_fields_split_on_commas():
    assert split_fields("a,b,c") == ("a", "b", "c")


def test_a_quoted_field_may_hold_a_comma():
    assert split_fields('a,"b,c",d') == ("a", "b,c", "d")


def test_a_doubled_quote_is_one_quote():
    assert split_fields('a,"say ""hi""",b') == ("a", 'say "hi"', "b")


def test_an_empty_field_is_kept():
    assert split_fields("a,,c") == ("a", "", "c")


def test_an_unclosed_quote_is_refused():
    with pytest.raises(ReportError, match="never closes"):
        split_fields('a,"b,c')


def test_a_quote_inside_a_field_is_refused():
    with pytest.raises(ReportError, match="may only open a field"):
        split_fields('a,b"c')


def test_a_table_needs_a_header():
    with pytest.raises(ReportError, match="needs a header"):
        Table((), ())


def test_a_column_needs_a_name():
    with pytest.raises(ReportError, match="needs a name"):
        Table(("a", " "), (("1", "2"),))


def test_two_columns_may_not_share_a_name():
    with pytest.raises(ReportError, match="share a name"):
        Table(("a", "a"), (("1", "2"),))


def test_a_short_row_is_refused_by_the_table():
    with pytest.raises(ReportError, match="line 2 holds 1 field"):
        Table(("a", "b"), (("1",),))


def test_a_table_counts_its_rows():
    assert len(small()) == 3


def test_a_column_is_read_by_name():
    assert small().column("region") == ("North", "North", "South")


def test_a_column_that_is_not_there_is_refused():
    with pytest.raises(ReportError, match="no column called 'ghost'"):
        small().column("ghost")


def test_an_empty_document_is_refused():
    with pytest.raises(ReportError, match="the table is empty"):
        parse_table("   \n")


def test_a_document_with_a_header_and_no_rows_is_refused():
    with pytest.raises(ReportError, match="and no rows"):
        parse_table(HEADER)


def test_a_short_line_names_its_line_number():
    with pytest.raises(ReportError, match="line 3 holds 2 field"):
        parse_table(HEADER + "A-1,North,2,10.00,1.50\nA-2,North\n")


def test_a_blank_line_inside_the_rows_is_refused():
    with pytest.raises(ReportError, match="line 3 is blank"):
        parse_table(HEADER + "A-1,North,2,10.00,1.50\n\nA-2,North,1,5.25,\n")


def test_trailing_blank_lines_are_ignored():
    assert len(parse_table(HEADER + ROWS + "\n\n")) == 3


def test_windows_line_endings_are_read():
    assert len(parse_table((HEADER + ROWS).replace("\n", "\r\n"))) == 3


def test_the_reader_trims_each_field():
    table = parse_table("a,b\n 1 , 2 \n")
    assert table.rows == (("1", "2"),)


def test_read_table_refuses_a_missing_file(tmp_path):
    with pytest.raises(ReportError, match="file not found"):
        read_table(tmp_path / "nope.csv")


def test_the_bundled_table_holds_twelve_rows():
    assert len(bundled()) == 12 and len(bundled().header) == 8


# --------------------------------------------------------------------------- #
# What a column holds
# --------------------------------------------------------------------------- #
def test_a_column_of_amounts_is_money():
    assert kind_of("price", ["1.00", "2.50"]) == "money"


def test_a_column_of_whole_numbers_is_a_count():
    assert kind_of("units", ["1", "22"]) == "count"


def test_a_column_of_words_is_text():
    assert kind_of("region", ["North", "South"]) == "text"


def test_a_column_of_numbers_and_words_is_text():
    assert kind_of("mixed", ["1", "North"]) == "text"


def test_a_column_that_mixes_amounts_and_counts_is_refused():
    with pytest.raises(ReportError, match="decide whether it is money or a "
                                         "count"):
        kind_of("price", ["1.00", "2"])


def test_a_column_empty_in_every_row_is_refused():
    with pytest.raises(ReportError, match="empty in every row"):
        kind_of("blank", ["", "  "])


def test_a_column_ignores_blanks_when_deciding():
    assert kind_of("price", ["1.00", "", "2.50"]) == "money"


def test_every_kind_is_one_of_three():
    assert set(KINDS) == {"text", "count", "money"}


def test_the_bundled_kinds_are_pinned():
    table = bundled()
    assert [(name, kind_of(name, table.column(name))) for name in table.header] \
        == [("order_id", "text"), ("region", "text"), ("channel", "text"),
            ("units", "count"), ("unit_price", "money"),
            ("shipping", "money"), ("discount", "money"), ("status", "text")]


# --------------------------------------------------------------------------- #
# One column, profiled
# --------------------------------------------------------------------------- #
def test_a_money_column_counts_its_values_and_gaps():
    column = profile(bundled(), "shipping")
    assert (column.present, column.missing) == (8, 4)
    assert column.rows == 12


def test_a_money_column_total_is_in_cents():
    assert profile(bundled(), "shipping").total == 2548


def test_a_money_mean_rounds_half_up():
    assert profile(bundled(), "shipping").mean() == 319


def test_a_count_mean_is_a_whole_number():
    assert profile(bundled(), "units").mean() == 2


def test_a_text_column_has_no_total_or_mean():
    column = profile(bundled(), "region")
    assert column.total is None and column.mean() is None


def test_a_text_column_has_no_statistic():
    assert profile(bundled(), "region").stat() is None


def test_a_column_over_the_gap_limit_is_flagged():
    assert profile(bundled(), "shipping").gap() is True


def test_a_column_under_the_gap_limit_is_not_flagged():
    assert profile(bundled(), "units").gap() is False


def test_the_gap_limit_is_twenty_per_cent():
    assert GAP_LIMIT == 20


def test_a_statistic_prints_its_denominator():
    assert profile(bundled(), "unit_price").stat().line() == \
        "unit_price: mean 47.55 over 12 of 12 rows"


def test_a_statistic_with_gaps_prints_them():
    assert profile(bundled(), "shipping").stat().line() == \
        "shipping: mean 3.19 over 8 of 12 rows (4 missing)"


def test_a_statistic_labels_its_unit():
    assert profile(bundled(), "units").stat().labelled() == "units (count)"


def test_a_statistic_keeps_integer_cents():
    stat = profile(bundled(), "shipping").stat()
    assert (stat.total, stat.n, stat.mean()) == (2548, 8, 319)


def test_a_statistic_refuses_to_average_nothing():
    with pytest.raises(ReportError, match="needs something to divide by"):
        Stat("x", "money", 100, 0, 12).mean()


def test_a_column_statistic_matches_its_column():
    column = profile(bundled(), "discount")
    assert column.stat() == Stat("discount", "money", 3875, 5, 12)


# --------------------------------------------------------------------------- #
# Groups
# --------------------------------------------------------------------------- #
def test_the_bundled_groups_are_pinned():
    groups, _ = group_rows(bundled())
    assert [(group.name, group.orders, group.units, group.revenue)
            for group in groups] == [
        ("East", 3, 8, 20065), ("North", 3, 5, 34349),
        ("South", 2, 5, 9997), ("West", 2, 6, 12558)]


def test_a_group_is_sorted_by_name():
    groups, _ = group_rows(bundled())
    assert [group.name for group in groups] == sorted(group.name
                                                     for group in groups)


def test_two_rows_are_excluded():
    _, excluded = group_rows(bundled())
    assert len(excluded) == 2


def test_an_excluded_row_names_its_line_and_its_field():
    _, excluded = group_rows(bundled())
    assert (excluded[0].line, excluded[0].order, excluded[0].reason) == \
        (5, "A-1004", "units is empty")


def test_a_row_with_no_region_is_excluded():
    _, excluded = group_rows(bundled())
    assert excluded[1].reason == "region is empty"


def test_a_group_prints_its_orders_units_and_revenue():
    groups, _ = group_rows(bundled())
    assert groups[0].line() == \
        "East         3 order(s)    8 unit(s) revenue     200.65"


def test_a_row_with_two_gaps_names_both():
    table = parse_table("order_id,region,units,unit_price\nA-1,,,1.00\n")
    _, excluded = group_rows(table)
    assert excluded[0].reason == "region is empty; units is empty"


def test_grouping_by_another_column_works():
    groups, excluded = group_rows(bundled(), key="channel")
    assert [group.name for group in groups] == ["partner", "retail", "web"]
    assert len(excluded) == 1


def test_grouping_by_a_missing_column_is_refused():
    with pytest.raises(ReportError, match="no column called 'ghost'"):
        group_rows(bundled(), key="ghost")


def test_growth_by_units_uses_the_same_arithmetic():
    groups, _ = group_rows(bundled())
    assert sum(group.units for group in groups) == 24


# --------------------------------------------------------------------------- #
# The report
# --------------------------------------------------------------------------- #
def test_the_report_profiles_every_column():
    assert len(build_report(bundled()).columns) == 8


def test_the_report_holds_one_statistic_per_number_column():
    assert len(build_report(bundled()).stats()) == 4


def test_the_report_looks_a_column_up():
    assert a_report().column("units").total == 26


def test_the_report_refuses_a_column_it_does_not_hold():
    with pytest.raises(ReportError, match="no column called 'ghost'"):
        a_report().column("ghost")


def test_the_report_flags_the_gappy_columns():
    assert a_report().flagged() == ("shipping", "discount")


def test_the_report_totals_revenue_in_cents():
    assert a_report().revenue() == 76969


def test_the_report_prints_revenue_as_money():
    assert money(a_report().revenue()) == "769.69"


def test_the_report_totals_units():
    assert a_report().units() == 24


def test_the_report_accounts_for_every_row():
    assert a_report().accounts() is True


def test_a_report_that_lost_a_group_does_not_account():
    report = a_report()
    assert replace(report, groups=report.groups[:-1]).accounts() is False


def test_every_statistic_line_names_its_denominator():
    assert all(" over " in stat.line() for stat in a_report().stats())


def test_the_report_table_starts_with_a_header_line():
    lines = a_report().table_lines()
    assert "column" in lines[0] and "missing" in lines[0] and len(lines) == 9


def test_the_report_csv_holds_one_line_per_column():
    lines = a_report().csv_lines()
    assert lines[0] == "column,kind,present,missing,total,mean,over,flagged"
    assert "shipping,money,8,4,2548,319,8,yes" in lines


def test_the_report_csv_marks_a_flag_only_when_it_is_one():
    assert "units,count,11,1,26,2,11,no" in a_report().csv_lines()


def test_the_report_remembers_its_key():
    assert build_report(bundled(), "channel").key == "channel"


# --------------------------------------------------------------------------- #
# The legacy lines
# --------------------------------------------------------------------------- #
def test_the_legacy_lines_are_pinned():
    assert LEGACY_SUMMARY == 'self.summary = dataframe.describe(include="all")'
    assert LEGACY_TYPES == 'report["Data Type"] = dataframe.dtypes.values'


def test_the_bundled_file_is_pinned_on_disk():
    assert SALES_FILE.read_text(encoding="utf-8").count("\n") == 13


def test_the_two_regular_expressions_describe_the_shapes():
    assert MONEY.match("12.34") and not MONEY.match("12")
    assert COUNT.match("12") and not COUNT.match("12.0")


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "every column's present and missing values add up to the rows",
    "every mean is printed with the number of values behind it",
    "every mean is recomputed from that column's own values",
    "no amount anywhere is a float",
    "every column total is the sum of that column",
    "every group's revenue is its units times its price",
    "exactly the columns over the gap limit are flagged",
    "the groups plus the excluded rows account for every row",
    "every excluded row names the field that is missing",
]


def test_the_audit_holds_nine_named_checks():
    assert [name for name, _ in audit(a_report())] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_report():
    assert problems(audit(a_report())) == []


def test_the_audit_is_repeatable():
    assert audit(a_report()) == audit(a_report())


def test_the_audit_catches_a_column_that_does_not_add_up():
    report = with_column(a_report(), "units", present=12)
    assert CHECK_NAMES[0] in problems(audit(report))


def test_the_audit_catches_a_mean_with_no_denominator():
    report = with_column(a_report(), "units", present=0, missing=12)
    assert CHECK_NAMES[1] in problems(audit(report))


def test_the_audit_catches_a_mean_that_does_not_match_its_column():
    report = with_column(a_report(), "shipping", present=7, missing=5)
    assert CHECK_NAMES[2] in problems(audit(report))


def test_the_audit_catches_a_total_stored_as_a_float():
    report = with_column(a_report(), "shipping", total=2548.0)
    assert CHECK_NAMES[3] in problems(audit(report))


def test_the_audit_does_not_raise_on_a_float_total():
    report = with_column(a_report(), "shipping", total=2548.0)
    assert len(audit(report)) == 9


def test_the_audit_catches_a_total_that_is_not_the_sum():
    report = with_column(a_report(), "shipping", total=2549)
    assert CHECK_NAMES[4] in problems(audit(report))


def test_the_audit_catches_a_group_whose_revenue_is_wrong():
    report = a_report()
    wrong = (replace(report.groups[0], revenue=report.groups[0].revenue + 1),) \
        + report.groups[1:]
    assert CHECK_NAMES[5] in problems(audit(replace(report, groups=wrong)))


def test_the_audit_catches_a_group_missing_an_order():
    report = a_report()
    wrong = (replace(report.groups[0], orders=report.groups[0].orders + 1),) \
        + report.groups[1:]
    assert CHECK_NAMES[5] in problems(audit(replace(report, groups=wrong)))


def test_the_audit_catches_a_wrong_flag_list():
    report = replace(a_report(), columns=a_report().columns)
    broken = replace(report, columns=tuple(
        replace(column, missing=0) if column.name == "shipping" else column
        for column in report.columns))
    assert CHECK_NAMES[6] in problems(audit(broken))


def test_the_audit_catches_a_lost_row():
    report = a_report()
    assert CHECK_NAMES[7] in problems(
        audit(replace(report, excluded=report.excluded[:1])))


def test_the_audit_catches_an_exclusion_without_a_reason():
    report = a_report()
    silent = replace(report.excluded[0], reason="")
    assert CHECK_NAMES[8] in problems(
        audit(replace(report, excluded=(silent,) + report.excluded[1:])))


def test_an_excluded_row_prints_nothing_by_itself():
    assert Excluded(2, "A-1", "units is empty").reason


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out and "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    assert all(ord(character) < 128 for character in capsys.readouterr().out)


def test_demo_shows_the_float_and_the_tie(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "0.10 + 0.20 = 0.30000000000000004" in out
    assert "round(318.5) = 318" in out
    assert "divide_half_up(2548, 8) = 319" in out


def test_demo_prints_every_column_with_its_denominator(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "shipping    money          8       4     25.48  mean 3.19 over 8 " \
           "of 12 rows (4 missing)" in out


def test_demo_shows_the_flagged_columns(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "shipping: 4 of 12 rows empty -- a mean here is over 8 value(s), " \
           "not 12" in out


def test_demo_shows_the_groups_and_the_accounting(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "total                      24 unit(s) revenue 769.69" in out
    assert "10 grouped + 2 excluded = 12 rows: yes" in out


def test_demo_shows_all_nine_checks(capsys):
    run_demo()
    assert "9/9 checks pass" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_prints_the_table_and_the_groups(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "  12 rows, 8 columns, grouped by region" in out
    assert "shipping    money          8       4     25.48" in out
    assert "  excluded line 5 A-1004: units is empty" in out


def test_cli_groups_by_another_column(capsys):
    assert cli.main(["--group", "channel"]) == 0
    out = capsys.readouterr().out
    assert "grouped by channel" in out and "partner      2 order(s)" in out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 9 and "FAIL" not in out


def test_cli_writes_the_csv(tmp_path, capsys):
    target = tmp_path / "report.csv"
    assert cli.main(["--csv", str(target)]) == 0
    capsys.readouterr()
    text = target.read_text(encoding="utf-8")
    assert text.startswith("column,kind,present,missing,total,mean,over,flagged")
    assert "shipping,money,8,4,2548,319,8,yes" in text


def test_cli_writes_the_json(tmp_path, capsys):
    target = tmp_path / "report.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["rows"] == 12 and payload["accounts"] is True
    assert payload["revenue_cents"] == 76969
    assert payload["gap_limit"] == 20
    assert payload["groups"][0]["revenue_text"] == "200.65"
    assert [entry["order"] for entry in payload["excluded"]] == ["A-1004",
                                                                "A-1007"]


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_reads_another_file(tmp_path, capsys):
    path = a_file(tmp_path, HEADER + ROWS)
    assert cli.main(["--data", str(path)]) == 0
    out = capsys.readouterr().out
    assert "  3 rows, 5 columns, grouped by region" in out
    assert "  2 grouped + 1 excluded = 3 rows" in out


def test_cli_a_missing_file_exits_two(tmp_path, capsys):
    assert cli.main(["--data", str(tmp_path / "nope.csv")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_a_mixed_column_exits_two(tmp_path, capsys):
    path = a_file(tmp_path, "a,b\n1.00,x\n2,x\n")
    assert cli.main(["--data", str(path)]) == 2
    assert "decide whether it is money or a count" in capsys.readouterr().err
