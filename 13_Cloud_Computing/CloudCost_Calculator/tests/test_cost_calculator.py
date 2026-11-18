"""Tests for the cloud cost lab: a bill is integer cents, a price is not."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import cost_calculator as module                           # noqa: E402
import main as cli                                          # noqa: E402
from cost_calculator import (                               # noqa: E402
    BUDGET_CENTS,
    FIELD,
    LEGACY_TIER,
    LEGACY_TOTAL,
    PRICE_SCALE,
    TIERS,
    BillLine,
    DomainError,
    audit,
    bill_total,
    budget_status,
    disagreements,
    divide_half_up,
    format_cents,
    format_price,
    legacy_bill_total,
    legacy_line_cents,
    legacy_tiered_cents,
    line_cents,
    measure,
    parse_bill,
    parse_price,
    problems,
    read_bill,
    run_demo,
    tiered_cents,
)

LINES = read_bill()
MEASURED = measure(LINES)


# --------------------------------------------------------------------------- #
# divide_half_up
# --------------------------------------------------------------------------- #
def test_divide_half_up_rounds_a_tie_up():
    assert divide_half_up(5, 2) == 3
    assert divide_half_up(25, 2) == 13


def test_divide_half_up_floors_below_the_tie():
    assert divide_half_up(7, 3) == 2


def test_divide_half_up_of_an_exact_division():
    assert divide_half_up(12, 4) == 3


def test_divide_half_up_rounds_a_negative_tie_away_from_zero():
    assert divide_half_up(-5, 2) == -3


def test_divide_half_up_of_zero():
    assert divide_half_up(0, 10) == 0


def test_divide_half_up_refuses_a_bad_denominator():
    with pytest.raises(DomainError, match="a denominator is positive"):
        divide_half_up(1, 0)
    with pytest.raises(DomainError, match="a denominator is a whole number"):
        divide_half_up(1, True)


def test_divide_half_up_refuses_a_float_numerator():
    with pytest.raises(DomainError, match="a numerator is a whole number"):
        divide_half_up(1.5, 2)


# --------------------------------------------------------------------------- #
# parse_price
# --------------------------------------------------------------------------- #
def test_parse_price_keeps_tenths_of_a_cent():
    assert parse_price("0.023") == 23
    assert parse_price("1.005") == 1005
    assert parse_price("12") == 12000
    assert parse_price("$2.50") == 2500
    assert parse_price("0.145") == 145
    assert parse_price("0.1") == 100
    assert parse_price("0.09") == 90
    assert parse_price(" 0.5 ") == 500
    assert parse_price("0") == 0
    assert parse_price("0.000") == 0


def test_parse_price_refuses_more_than_three_decimals():
    with pytest.raises(DomainError, match="at most three decimals"):
        parse_price("0.0234")


def test_parse_price_refuses_a_word():
    with pytest.raises(DomainError, match="dollar amount"):
        parse_price("free")


def test_parse_price_refuses_a_malformed_number():
    with pytest.raises(DomainError, match="dollar amount"):
        parse_price("1.")
    with pytest.raises(DomainError, match="dollar amount"):
        parse_price("1..2")


def test_parse_price_refuses_a_negative_price():
    with pytest.raises(DomainError, match="not negative"):
        parse_price("-0.01")


def test_parse_price_refuses_a_float_argument():
    with pytest.raises(DomainError, match="a price is text"):
        parse_price(1.5)


def test_parse_price_refuses_a_blank_price():
    with pytest.raises(DomainError, match="not blank"):
        parse_price("   ")


# --------------------------------------------------------------------------- #
# format_price and format_cents
# --------------------------------------------------------------------------- #
def test_format_price_keeps_a_tenth_of_a_cent():
    assert format_price(145) == "$0.145"
    assert format_price(1005) == "$1.005"
    assert format_price(100) == "$0.10"
    assert format_price(0) == "$0.00"
    assert format_price(23) == "$0.023"
    assert format_price(1000) == "$1.00"
    assert format_price(15) == "$0.015"


def test_format_price_refuses_a_float():
    with pytest.raises(DomainError, match="a price is a whole number"):
        format_price(1.5)


def test_format_cents_never_uses_a_float():
    assert format_cents(5716) == "$57.16"
    assert format_cents(5) == "$0.05"
    assert format_cents(0) == "$0.00"
    assert format_cents(100) == "$1.00"
    assert format_cents(1) == "$0.01"
    assert format_cents(-123) == "-$1.23"


def test_format_cents_refuses_a_bool():
    with pytest.raises(DomainError, match="whole number"):
        format_cents(True)


# --------------------------------------------------------------------------- #
# line_cents and the legacy line
# --------------------------------------------------------------------------- #
def test_line_cents_rounds_half_up():
    assert line_cents(1, 1005) == 101
    assert line_cents(3, 145) == 44
    assert line_cents(7, 45) == 32
    assert line_cents(120, 90) == 1080
    assert line_cents(250, 23) == 575
    assert line_cents(0, 145) == 0


def test_line_cents_refuses_a_negative_quantity():
    with pytest.raises(DomainError, match="a quantity is not negative"):
        line_cents(-1, 100)


def test_line_cents_refuses_a_negative_price():
    with pytest.raises(DomainError, match="a price is not negative"):
        line_cents(1, -100)


def test_line_cents_refuses_a_float():
    with pytest.raises(DomainError, match="a quantity is a whole number"):
        line_cents(1.0, 100)


def test_the_legacy_line_rounds_100_5_down():
    assert legacy_line_cents(1, 1.005) == 100


def test_the_legacy_line_rounds_43_5_down():
    assert legacy_line_cents(3, 0.145) == 43


def test_the_legacy_line_agrees_on_a_clean_price():
    assert legacy_line_cents(250, 0.023) == 575


def test_the_two_lines_disagree_by_one_cent():
    assert line_cents(1, 1005) - legacy_line_cents(1, 1.005) == 1


def test_the_legacy_line_refuses_a_text_price():
    with pytest.raises(DomainError, match="a legacy price is a float"):
        legacy_line_cents(1, "0.145")


# --------------------------------------------------------------------------- #
# BillLine
# --------------------------------------------------------------------------- #
def test_a_line_holds_four_fields():
    row = BillLine("compute", "c7.large", 730, 13)
    assert (row.service, row.sku, row.quantity, row.price_tenths) == \
        ("compute", "c7.large", 730, 13)


def test_a_line_total_and_legacy_total():
    row = BillLine("requests", "api-call", 3, 145)
    assert (row.total_cents(), row.legacy_cents()) == (44, 43)


def test_a_line_knows_whether_the_two_agree():
    assert BillLine("requests", "api-call", 3, 145).agrees() is False
    assert BillLine("storage", "gp3", 250, 23).agrees() is True


def test_a_line_marks_a_disagreement():
    assert BillLine("requests", "api-call", 3, 145).row().endswith("  <-")
    assert not BillLine("storage", "gp3", 250, 23).row().endswith("<-")


def test_a_line_head_shows_the_price_in_dollars():
    assert "$0.145" in BillLine("requests", "api-call", 3, 145).head()


def test_a_line_refuses_a_blank_field():
    with pytest.raises(DomainError, match="a service is text, and not blank"):
        BillLine("  ", "sku", 1, 1)
    with pytest.raises(DomainError, match="a sku is text, and not blank"):
        BillLine("compute", "  ", 1, 1)


def test_a_line_refuses_a_negative_quantity():
    with pytest.raises(DomainError, match="a quantity is not negative"):
        BillLine("compute", "sku", -1, 1)


def test_a_line_refuses_a_bad_price():
    with pytest.raises(DomainError, match="a price is a whole number"):
        BillLine("compute", "sku", 1, 1.5)
    with pytest.raises(DomainError, match="a price is not negative"):
        BillLine("compute", "sku", 1, -1)


# --------------------------------------------------------------------------- #
# parse_bill and read_bill
# --------------------------------------------------------------------------- #
def test_parse_bill_reads_four_fields():
    rows = parse_bill("compute | c7.large | 730 | 0.013\n")
    assert rows == (BillLine("compute", "c7.large", 730, 13),)


def test_parse_bill_accepts_no_spaces():
    assert parse_bill("a|b|1|0.5")[0].price_tenths == 500


def test_parse_bill_skips_comments_blanks_and_windows_endings():
    text = "# a note\n\r\na | b | 1 | 0.1\r\nc | d | 2 | 0.2\r\n"
    assert len(parse_bill(text)) == 2


def test_parse_bill_refuses_the_wrong_field_count():
    with pytest.raises(DomainError, match="four fields are needed"):
        parse_bill("compute | c7 | 1\n")
    with pytest.raises(DomainError, match="four fields are needed"):
        parse_bill("compute | c7 | 1 | 0.1 | extra\n")


def test_parse_bill_names_the_line_it_could_not_read():
    with pytest.raises(DomainError, match="line 2:"):
        parse_bill("a | b | 1 | 0.1\nbroken\n")


def test_parse_bill_refuses_a_word_where_a_quantity_should_be():
    with pytest.raises(DomainError, match="not a whole quantity"):
        parse_bill("a | b | many | 0.1\n")


def test_parse_bill_refuses_a_price_with_four_decimals():
    with pytest.raises(DomainError, match="at most three decimals"):
        parse_bill("a | b | 1 | 0.0234\n")


def test_parse_bill_refuses_an_empty_bill():
    with pytest.raises(DomainError, match="at least one line"):
        parse_bill("# nothing\n")


def test_the_field_separator_is_a_pipe():
    assert FIELD == "|"


def test_the_bundled_bill_has_seven_lines():
    assert len(LINES) == 7
    assert LINES[0].service == "compute"


def test_read_bill_refuses_a_missing_file(tmp_path):
    with pytest.raises(DomainError, match="file not found"):
        read_bill(tmp_path / "nope.txt")


def test_read_bill_accepts_its_own_file(tmp_path):
    path = tmp_path / "bill.txt"
    path.write_bytes(b"compute | c7 | 1 | 0.1\n")
    assert read_bill(path)[0].quantity == 1


# --------------------------------------------------------------------------- #
# Totals
# --------------------------------------------------------------------------- #
def test_the_integer_bill_is_5716_cents():
    assert bill_total(LINES) == 5716


def test_the_float_bill_is_5714_cents():
    assert legacy_bill_total(LINES) == 5714


def test_the_two_bills_differ_by_two_cents():
    assert bill_total(LINES) - legacy_bill_total(LINES) == 2


def test_two_rows_disagree_by_one_cent_each():
    rows = disagreements(LINES)
    assert [row.service for row in rows] == ["requests", "archive"]
    assert [row.total_cents() - row.legacy_cents() for row in rows] == [1, 1]


def test_an_empty_bill_totals_zero():
    assert bill_total(()) == 0 and legacy_bill_total(()) == 0


def test_a_total_refuses_something_that_is_not_a_line():
    with pytest.raises(DomainError, match="a bill holds lines"):
        bill_total(("compute",))


# --------------------------------------------------------------------------- #
# Tiered pricing
# --------------------------------------------------------------------------- #
def test_the_tier_table_is_three_tiers():
    assert TIERS == ((100, 25), (400, 15), (None, 9))


def test_zero_units_cost_nothing():
    assert tiered_cents(0) == 0


def test_the_first_tier_holds_one_hundred_units():
    assert tiered_cents(100) == 250


def test_one_unit_past_the_boundary_takes_the_next_rate():
    assert tiered_cents(101) == 252


def test_the_second_boundary_is_priced_inside_the_second_tier():
    assert tiered_cents(500) == 850


def test_five_hundred_and_fifty_units_are_billed_tier_by_tier():
    assert tiered_cents(550) == 895


def test_the_legacy_shortcut_applies_the_marginal_rate_to_every_unit():
    assert legacy_tiered_cents(550) == 495
    assert tiered_cents(550) - legacy_tiered_cents(550) == 400


def test_a_custom_table_is_billed_the_same_way():
    table = ((10, 25), (None, 9))
    assert tiered_cents(10, table) == 25
    assert tiered_cents(11, table) == 26


def test_tiered_cents_refuses_negative_units():
    with pytest.raises(DomainError, match="not negative"):
        tiered_cents(-1)


def test_tiered_cents_refuses_a_bad_table():
    with pytest.raises(DomainError, match="at least one tier"):
        tiered_cents(5, ())
    with pytest.raises(DomainError, match="only the last tier"):
        tiered_cents(5, ((None, 9), (10, 5)))
    with pytest.raises(DomainError, match="a tier width is positive"):
        tiered_cents(5, ((0, 25), (None, 9)))


def test_tiered_cents_refuses_a_table_that_leaves_units_unpriced():
    with pytest.raises(DomainError, match="leaves 1 unit"):
        tiered_cents(11, ((10, 25),))


def test_the_legacy_tier_table_is_transcribed():
    assert LEGACY_TIER == "return round(units * tiers[-1][1] / 10)"


# --------------------------------------------------------------------------- #
# budget_status
# --------------------------------------------------------------------------- #
def test_a_budget_under_the_bill_is_over():
    assert budget_status(5716, 5000) == "over by $7.16"


def test_a_budget_over_the_bill_is_under():
    assert budget_status(4985, 5000) == "under by $0.15"


def test_a_bill_exactly_on_budget_says_so():
    assert budget_status(5000, 5000) == "on budget"


def test_the_default_budget_is_fifty_dollars():
    assert BUDGET_CENTS == 5000


def test_a_budget_refuses_bad_input():
    with pytest.raises(DomainError, match="a budget is not negative"):
        budget_status(1, -1)
    with pytest.raises(DomainError, match="a budget is a whole number"):
        budget_status(1, 2.5)


# --------------------------------------------------------------------------- #
# measure
# --------------------------------------------------------------------------- #
def test_measure_pins_the_prices():
    assert MEASURED["price_1_005"] == 1005
    assert MEASURED["price_0_023"] == 23


def test_measure_pins_the_half_up_lines():
    assert MEASURED["line_1005"] == 101
    assert MEASURED["legacy_line_1005"] == 100


def test_measure_pins_the_bill_totals():
    assert MEASURED["total"] == 5716
    assert MEASURED["legacy_total"] == 5714


def test_measure_pins_the_tiers():
    assert (MEASURED["tiers_100"], MEASURED["tiers_101"],
            MEASURED["tiers_550"]) == (250, 252, 895)
    assert MEASURED["legacy_tiers_550"] == 495


def test_measure_pins_the_rendered_values():
    assert MEASURED["formatted_total"] == "$57.16"
    assert MEASURED["budget"] == "over by $7.16"
    assert MEASURED["differing"] == ["requests", "archive"]


def test_measure_reads_only_the_lines_it_was_given():
    small = measure((BillLine("compute", "c7", 730, 13),))
    assert small["total"] == 949 and small["differing"] == []


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "a price keeps a tenth of a cent",
    "a line rounds half up, not by a float",
    "three at a half cent round up",
    "a bill is not the sum of its floats",
    "two rows disagree",
    "every line rebuilds from its fields",
    "a tier boundary keeps its last unit",
    "one unit past the boundary takes the next rate",
    "each tier rounds at its own boundary",
    "the marginal rate on every unit is the legacy error",
    "a bill is printed from integer cents",
    "a budget is compared in cents",
    "a price is never a float",
]


class BrokenLine:
    """A BillLine whose total is always zero -- the control for check 6."""

    def __init__(self, service, sku, quantity, price_tenths):
        self.quantity = quantity

    def total_cents(self):
        return 0


def corrupted(**changes) -> dict:
    payload = dict(MEASURED)
    payload.update(changes)
    return payload


def test_the_audit_holds_thirteen_named_checks():
    checks = audit(MEASURED, LINES)
    assert [name for name, _ in checks] == CHECK_NAMES
    assert problems(checks) == []


def test_the_audit_is_repeatable():
    assert audit(MEASURED, LINES) == audit(MEASURED, LINES)


def test_the_audit_catches_a_price_that_lost_its_tenths():
    checks = audit(corrupted(price_0_023=2, precise_refused=False), LINES)
    assert CHECK_NAMES[0] in problems(checks)


def test_the_audit_catches_a_float_line_rounding():
    checks = audit(corrupted(line_1005=100), LINES)
    assert CHECK_NAMES[1] in problems(checks)


def test_the_audit_catches_43_cents_for_three_quarters_of_a_cent():
    checks = audit(corrupted(line_145_x3=43), LINES)
    assert CHECK_NAMES[2] in problems(checks)


def test_the_audit_catches_a_total_that_matches_the_floats():
    checks = audit(corrupted(total=5714, legacy_total=5714), LINES)
    assert CHECK_NAMES[3] in problems(checks)


def test_the_audit_catches_a_missing_disagreement():
    checks = audit(corrupted(differing=["requests"]), LINES)
    assert CHECK_NAMES[4] in problems(checks)


def test_the_audit_catches_a_line_that_does_not_rebuild():
    checks = audit(MEASURED, LINES, make_line=BrokenLine)
    assert CHECK_NAMES[5] in problems(checks)


def test_the_audit_catches_a_tier_boundary_off_by_one():
    checks = audit(corrupted(tiers_100=251), LINES)
    assert CHECK_NAMES[6] in problems(checks)


def test_the_audit_catches_a_wrong_tier_crossing_and_total():
    checks = audit(corrupted(tiers_101=251, tiers_550=894), LINES)
    assert CHECK_NAMES[7] in problems(checks)
    assert CHECK_NAMES[8] in problems(checks)


def test_the_audit_catches_the_marginal_rate_being_called_correct():
    checks = audit(corrupted(legacy_tiers_550=895), LINES)
    assert CHECK_NAMES[9] in problems(checks)


def test_the_audit_catches_a_bill_printed_with_one_decimal():
    checks = audit(corrupted(formatted_total="$57.2"), LINES)
    assert CHECK_NAMES[10] in problems(checks)


def test_the_audit_catches_a_budget_in_the_wrong_direction():
    checks = audit(corrupted(budget="under by $7.16"), LINES)
    assert CHECK_NAMES[11] in problems(checks)


def test_the_audit_catches_a_float_price_that_was_accepted():
    checks = audit(corrupted(float_input_refused=False), LINES)
    assert CHECK_NAMES[12] in problems(checks)


def test_a_missing_measurement_is_a_failure_not_a_traceback():
    payload = corrupted()
    del payload["tiers_550"]
    checks = audit(payload, LINES)
    assert CHECK_NAMES[8] in problems(checks)
    assert len(checks) == len(CHECK_NAMES)


def test_each_check_is_falsifiable_from_its_own_measurement():
    caught = set()
    caught |= set(problems(audit(corrupted(price_0_023=2), LINES)))
    caught |= set(problems(audit(corrupted(line_1005=100), LINES)))
    caught |= set(problems(audit(corrupted(line_145_x3=43), LINES)))
    caught |= set(problems(audit(corrupted(total=5714), LINES)))
    caught |= set(problems(audit(corrupted(differing=[]), LINES)))
    caught |= set(problems(audit(MEASURED, LINES, make_line=BrokenLine)))
    caught |= set(problems(audit(corrupted(tiers_100=0), LINES)))
    caught |= set(problems(audit(corrupted(tiers_101=0), LINES)))
    caught |= set(problems(audit(corrupted(tiers_550=0), LINES)))
    caught |= set(problems(audit(corrupted(legacy_tiers_550=0), LINES)))
    caught |= set(problems(audit(corrupted(formatted_total=""), LINES)))
    caught |= set(problems(audit(corrupted(budget=""), LINES)))
    caught |= set(problems(audit(corrupted(float_input_refused=False), LINES)))
    assert caught == set(CHECK_NAMES)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero_and_ends_with_the_two_lines(capsys):
    assert run_demo() == 0
    lines = capsys.readouterr().out.strip().split("\n")
    assert lines[-1] == "Demo completed successfully."
    assert lines[-2].startswith("Cross-checks OK: ")


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    assert all(ord(character) < 128 for character in capsys.readouterr().out)


def test_demo_shows_the_legacy_total(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "CLOUD COST LAB" in out and "total += line.quantity" in out


def test_demo_reports_all_thirteen_checks_and_the_gap(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "13/13 checks pass" in out
    assert "5716 cents here, 5714 cents from floats" in out


def test_the_legacy_total_is_transcribed():
    assert module.LEGACY_TOTAL.startswith("total = 0.0")
    assert "round(total * 100)" in LEGACY_TOTAL
    assert PRICE_SCALE == 10


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


def test_cli_lists_the_bundled_bill(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "7 line(s)" in out and "compute" in out


def test_cli_prints_both_totals(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "$57.16 (5716 cents)" in out and "$57.14 (5714 cents)" in out


def test_cli_prints_the_budget(capsys):
    assert cli.main(["--budget", "6000"]) == 0
    assert "under by $2.84" in capsys.readouterr().out


def test_cli_prices_tiers(capsys):
    assert cli.main(["--tier-units", "550"]) == 0
    out = capsys.readouterr().out
    assert "895 cents tier by tier" in out
    assert "495 cents at the marginal rate" in out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 13 and "FAIL" not in out


def test_cli_writes_the_bill_as_json(tmp_path, capsys):
    target = tmp_path / "bill.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["total_cents"] == 5716
    assert payload["legacy_total_cents"] == 5714
    requests = [row for row in payload["lines"]
                if row["service"] == "requests"][0]
    assert requests["cents"] == 44 and requests["legacy_cents"] == 43


def test_cli_json_carries_the_checks(tmp_path, capsys):
    target = tmp_path / "bill.json"
    assert cli.main(["--audit", "--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["measurements"]["tiers_550"] == 895
    assert len(payload["checks"]) == 13
    assert all(check["ok"] for check in payload["checks"])


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_refuses_a_missing_bill(tmp_path, capsys):
    assert cli.main(["--file", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_refuses_a_bad_price(tmp_path, capsys):
    path = tmp_path / "bill.txt"
    path.write_bytes(b"compute | c7 | 1 | 0.0234\n")
    assert cli.main(["--file", str(path)]) == 2
    assert "at most three decimals" in capsys.readouterr().err


def test_cli_refuses_a_negative_budget_or_tier_count(capsys):
    assert cli.main(["--budget", "-1"]) == 2
    assert "a budget is not negative" in capsys.readouterr().err
    assert cli.main(["--tier-units", "-5"]) == 2
    assert "not negative" in capsys.readouterr().err


def test_cli_refuses_a_budget_that_is_not_a_number(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(["--budget", "lots"])
    assert raised.value.code == 2
