"""Tests for the calculator: a display is not a number, and eval is not one."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import calculator as module                                 # noqa: E402
import main as cli                                          # noqa: E402
from calculator import (                                    # noqa: E402
    LEGACY_CALCULATE,
    MAX_DEPTH,
    MAX_INTEGER_DIGITS,
    PLACES,
    CalcError,
    Parser,
    Result,
    Token,
    audit,
    compare,
    divide_half_up,
    evaluate,
    exact,
    legacy_calculate,
    parse_expressions,
    problems,
    read_expressions,
    render,
    run_demo,
    tokenize,
)

EXPRESSIONS = read_expressions()


def a_result(expression: str = "2+2", legacy: str = "4", shown: str = "4",
             places: int = 2) -> Result:
    return Result(expression, legacy, shown, places)


# --------------------------------------------------------------------------- #
# Tokens
# --------------------------------------------------------------------------- #
def test_a_token_holds_a_kind_its_text_and_its_place():
    token = Token("number", "12", 3)
    assert (token.kind, token.text, token.at) == ("number", "12", 3)


def test_a_token_line_names_all_three():
    assert Token("operator", "+", 4).line() == "operator '+' at 4"


def test_a_token_of_an_unknown_kind_is_refused():
    with pytest.raises(CalcError, match="is not a token kind"):
        Token("digit", "1", 0)


def test_a_token_with_no_text_is_refused():
    with pytest.raises(CalcError, match="carries its text"):
        Token("number", "", 0)


def test_a_token_before_the_start_is_refused():
    with pytest.raises(CalcError, match="position of at least 0"):
        Token("number", "1", -1)


# --------------------------------------------------------------------------- #
# tokenize
# --------------------------------------------------------------------------- #
def test_tokenize_reads_whole_numbers():
    assert [token.text for token in tokenize("12 7")] == ["12", "7"]


def test_tokenize_reads_decimals():
    assert [token.text for token in tokenize("3.25")] == ["3.25"]


def test_tokenize_reads_a_leading_point():
    assert [token.text for token in tokenize(".5")] == [".5"]


def test_tokenize_reads_a_trailing_point():
    assert [token.text for token in tokenize("5.")] == ["5."]


def test_tokenize_reads_every_operator():
    assert [token.text for token in tokenize("+-*/%^")] == \
        ["+", "-", "*", "/", "%", "^"]


def test_tokenize_reads_brackets():
    assert [token.kind for token in tokenize("(1)")] == \
        ["open", "number", "close"]


def test_tokenize_skips_whitespace():
    assert len(tokenize("  1  +  2  ")) == 3


def test_tokenize_refuses_two_decimal_points():
    with pytest.raises(CalcError, match="one decimal point"):
        tokenize("1..2")


def test_tokenize_refuses_a_lone_point():
    with pytest.raises(CalcError, match="needs a digit"):
        tokenize(".")


def test_tokenize_refuses_a_letter_and_names_the_place():
    with pytest.raises(CalcError, match="'a' at 1"):
        tokenize("2a")


def test_tokenize_refuses_an_empty_expression():
    with pytest.raises(CalcError, match="at least one token"):
        tokenize("   ")


def test_tokenize_refuses_something_that_is_not_text():
    with pytest.raises(CalcError, match="an expression is text"):
        tokenize(12)


def test_tokenize_refuses_a_function_name():
    with pytest.raises(CalcError, match="not part of an expression"):
        tokenize("len('ab')")


# --------------------------------------------------------------------------- #
# evaluate
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,expected", [
    ("1+2", "3"), ("7-9", "-2"), ("6*7", "42"), ("9/3", "3"), ("7%4", "3"),
    ("2^10", "1024"), ("2+3*4", "14"), ("(2+3)*4", "20"),
    ("2^3^2", "512"), ("-2^2", "-4"), ("-2*3", "-6"), ("1--2", "3"),
    ("+5", "5"), ("2^-1", "0.5"), ("0.1+0.2", "0.3"),
])
def test_evaluate_answers_the_arithmetic(text, expected):
    assert evaluate(text) == Decimal(expected)


def test_evaluate_keeps_thirty_four_digits_of_working_precision():
    assert len(exact(evaluate("1/3"))) == 36            # "0." and 34 digits


def test_evaluate_refuses_division_by_zero():
    with pytest.raises(CalcError, match="division by zero"):
        evaluate("10/0")


def test_evaluate_refuses_a_remainder_by_zero():
    with pytest.raises(CalcError, match="remainder by zero"):
        evaluate("5%0")


def test_evaluate_refuses_a_fractional_exponent():
    with pytest.raises(CalcError, match="not a whole number"):
        evaluate("2^0.5")


def test_evaluate_refuses_an_expression_that_ends_on_an_operator():
    with pytest.raises(CalcError, match="ends where a value was expected"):
        evaluate("2+")


def test_evaluate_refuses_a_closing_bracket_it_never_opened():
    with pytest.raises(CalcError, match="follows a complete expression"):
        evaluate("2+3)")


def test_evaluate_refuses_an_unclosed_bracket():
    with pytest.raises(CalcError, match="ends where a value was expected"):
        evaluate("(2+3")


def test_evaluate_refuses_brackets_that_nest_too_deeply():
    text = "(" * (MAX_DEPTH + 4) + "1" + ")" * (MAX_DEPTH + 4)
    with pytest.raises(CalcError, match="nest"):
        evaluate(text)


def test_evaluate_accepts_brackets_at_the_limit():
    text = "(" * MAX_DEPTH + "1" + ")" * MAX_DEPTH
    assert evaluate(text) == Decimal(1)


def test_evaluate_refuses_two_operators_in_a_row():
    with pytest.raises(CalcError, match="operator where a number"):
        evaluate("2*/3")


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #
def test_render_rounds_half_up():
    assert render(Decimal("2.675"), 2) == "2.68"


def test_render_rounds_a_tie_away_from_zero():
    assert render(Decimal("2.5"), 0) == "3"
    assert render(Decimal("-2.5"), 0) == "-3"


def test_render_is_not_half_even():
    assert render(Decimal("2.5"), 0) == "3"
    assert round(2.5) == 2


def test_render_strips_trailing_zeros():
    assert render(Decimal("1.500"), 2) == "1.5"


def test_render_strips_a_bare_point():
    assert render(Decimal("2.000"), 2) == "2"


def test_render_shows_zero_for_a_negative_zero():
    assert render(Decimal("-0.001"), 2) == "0"


def test_render_truncates_a_repeating_quotient():
    assert render(Decimal(1) / Decimal(3), 6) == "0.333333"


def test_render_refuses_a_result_wider_than_the_display():
    with pytest.raises(CalcError, match="digits before the point"):
        render(Decimal(10) ** MAX_INTEGER_DIGITS, 2)


def test_render_accepts_a_result_exactly_as_wide_as_the_display():
    assert render(Decimal(10) ** (MAX_INTEGER_DIGITS - 1), 0) == \
        "1" + "0" * (MAX_INTEGER_DIGITS - 1)


def test_render_refuses_a_value_that_is_not_a_decimal():
    with pytest.raises(CalcError, match="shows a Decimal"):
        render(2.675)


def test_render_refuses_a_nan():
    with pytest.raises(CalcError, match="not finite"):
        render(Decimal("NaN"))


def test_render_refuses_an_infinity():
    with pytest.raises(CalcError, match="not finite"):
        render(Decimal("Infinity"))


def test_render_refuses_more_places_than_it_has():
    with pytest.raises(CalcError, match="between 0 and 12"):
        render(Decimal("1"), 13)


def test_render_refuses_a_negative_place_count():
    with pytest.raises(CalcError, match="between 0 and 12"):
        render(Decimal("1"), -1)


def test_render_defaults_to_two_places():
    assert PLACES == 2 and render(Decimal("1.239")) == "1.24"


# --------------------------------------------------------------------------- #
# divide_half_up
# --------------------------------------------------------------------------- #
def test_divide_half_up_rounds_a_tie_up():
    assert divide_half_up(2675, 1000, 2) == 268


def test_divide_half_up_floors_below_the_tie():
    assert divide_half_up(2674, 1000, 2) == 267


def test_divide_half_up_rounds_a_negative_tie_away_from_zero():
    assert divide_half_up(-2675, 1000, 2) == -268


def test_divide_half_up_at_no_places():
    assert divide_half_up(5, 2, 0) == 3


def test_divide_half_up_drops_a_small_fraction():
    assert divide_half_up(1, 1000, 2) == 0


def test_divide_half_up_refuses_a_zero_denominator():
    with pytest.raises(CalcError, match="division by zero"):
        divide_half_up(1, 0, 2)


def test_divide_half_up_refuses_a_float_numerator():
    with pytest.raises(CalcError, match="a numerator is a whole number"):
        divide_half_up(1.5, 2, 2)


def test_divide_half_up_refuses_a_true_as_a_number():
    with pytest.raises(CalcError, match="a numerator is a whole number"):
        divide_half_up(True, 2, 2)


def test_divide_half_up_refuses_too_many_places():
    with pytest.raises(CalcError, match="between 0 and 12"):
        divide_half_up(1, 2, 13)


# --------------------------------------------------------------------------- #
# The legacy path
# --------------------------------------------------------------------------- #
def test_the_legacy_caret_is_exclusive_or():
    assert legacy_calculate("2 ^ 3") == 1


def test_the_legacy_adder_returns_a_float():
    assert legacy_calculate("0.1 + 0.2") != 0.3


def test_the_legacy_adder_shows_seventeen_digits():
    assert repr(legacy_calculate("0.1 + 0.2")) == "0.30000000000000004"


def test_the_legacy_reader_answers_an_ordinary_sum():
    assert legacy_calculate("1 + 1") == 2


def test_the_legacy_reader_raises_on_division_by_zero():
    with pytest.raises(ZeroDivisionError):
        legacy_calculate("10 / 0")


def test_the_legacy_reader_has_no_names_to_call():
    with pytest.raises(NameError):
        legacy_calculate("len('ab')")


def test_the_transcribed_legacy_source_is_the_two_lines():
    assert LEGACY_CALCULATE.startswith("def calculate(expression):")
    assert LEGACY_CALCULATE.rstrip().endswith("return eval(expression)")


# --------------------------------------------------------------------------- #
# Reading the bundle
# --------------------------------------------------------------------------- #
def test_the_bundle_holds_twelve_expressions():
    assert len(EXPRESSIONS) == 12


def test_parse_expressions_skips_a_comment():
    assert parse_expressions("; note\n2+2\n") == ("2+2",)


def test_parse_expressions_keeps_a_value_after_a_semicolon_off():
    assert parse_expressions("2+2 ; this is not a comment\n") == ("2+2",)


def test_parse_expressions_skips_blank_lines():
    assert parse_expressions("\n2+2\n\n") == ("2+2",)


def test_parse_expressions_reads_windows_line_endings():
    assert parse_expressions("1+1\r\n2+2\r\n") == ("1+1", "2+2")


def test_parse_expressions_refuses_a_hash_comment():
    with pytest.raises(CalcError, match="comment starts with ';'"):
        parse_expressions("# note\n2+2\n")


def test_parse_expressions_refuses_an_empty_bundle():
    with pytest.raises(CalcError, match="at least one expression"):
        parse_expressions("; nothing but a comment\n")


def test_parse_expressions_refuses_something_that_is_not_text():
    with pytest.raises(AttributeError):
        parse_expressions(12)


def test_a_missing_bundle_is_refused(tmp_path):
    with pytest.raises(CalcError, match="file not found"):
        read_expressions(tmp_path / "nope.txt")


def test_read_expressions_accepts_its_own_file(tmp_path):
    path = tmp_path / "expressions.txt"
    path.write_bytes(b"1+1\n3*3\n")
    assert read_expressions(path) == ("1+1", "3*3")


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
def test_a_result_holds_the_expression_the_legacy_answer_and_the_display():
    result = a_result()
    assert (result.expression, result.legacy, result.shown) == ("2+2", "4", "4")


def test_a_result_line_shows_both_answers():
    assert a_result().line() == "2+2                eval=4                      shows=4"


def test_a_result_with_no_expression_is_refused():
    with pytest.raises(CalcError, match="names the expression"):
        a_result(expression="  ")


def test_a_result_with_no_legacy_text_is_refused():
    with pytest.raises(CalcError, match="legacy answer is text"):
        a_result(legacy=4)


def test_a_result_with_no_digits_is_refused():
    with pytest.raises(CalcError, match="carries the digits"):
        a_result(shown="")


def test_a_result_with_a_float_place_count_is_refused():
    with pytest.raises(CalcError, match="place count is a whole number"):
        a_result(places=2.0)


def test_a_crash_always_differs():
    assert a_result(legacy="crash").differs() is True


def test_a_refusal_always_differs():
    assert a_result(shown="refused: division by zero").differs() is True


def test_an_exact_agreement_does_not_differ():
    assert a_result(legacy="4", shown="4").differs() is False


def test_a_rounded_spelling_does_not_differ():
    assert a_result("0.1+0.2", "0.30000000000000004", "0.3").differs() is False


def test_an_answer_that_survives_rounding_differs():
    assert a_result("2^3", "1", "8").differs() is True


# --------------------------------------------------------------------------- #
# compare
# --------------------------------------------------------------------------- #
def test_compare_answers_one_row_per_expression():
    assert len(compare(EXPRESSIONS)) == len(EXPRESSIONS)


def test_compare_records_a_division_by_zero_as_a_crash():
    rows = compare(("10/0",))
    assert rows[0].legacy == "crash" and rows[0].shown.startswith("refused:")


def test_compare_records_the_caret_as_one():
    rows = compare(("2^3",))
    assert rows[0].legacy == "1" and rows[0].shown == "8"


def test_compare_carries_the_place_count_it_was_given():
    assert compare(("1/3",), 4)[0].places == 4


def test_compare_shows_four_places_when_asked():
    assert compare(("1/3",), 4)[0].shown == "0.3333"


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "the legacy adder shows seventeen digits",
    "the legacy caret is exclusive or",
    "a division by zero is a sentence",
    "rounding is half-up, not half-even",
    "multiplication binds tighter than addition",
    "power is right-associative",
    "unary minus binds looser than power",
    "brackets change the answer",
    "a result wider than the display is refused",
    "every expression produced one row",
    "two routes to the same hundredths agree",
]

ROWS = compare(EXPRESSIONS)
REFUSALS = [(row.expression, row.shown) for row in ROWS
            if row.shown.startswith("refused:")]


def real_checks():
    return audit(ROWS, REFUSALS)


def test_the_audit_holds_eleven_named_checks():
    assert [name for name, _ in real_checks()] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_expressions():
    assert problems(real_checks()) == []


def test_the_audit_is_repeatable():
    assert real_checks() == real_checks()


def swapped(expression: str, **fields):
    """The bundled rows with one row's fields replaced, past the constructor."""
    rows = []
    for row in ROWS:
        if row.expression.replace(" ", "") == expression.replace(" ", ""):
            clone = object.__new__(Result)
            for field in ("expression", "legacy", "shown", "places"):
                object.__setattr__(clone, field,
                                   fields.get(field, getattr(row, field)))
            rows.append(clone)
        else:
            rows.append(row)
    return tuple(rows)


def test_the_audit_catches_a_float_that_happens_to_print_cleanly():
    checks = audit(swapped("0.1+0.2", legacy="0.3"), REFUSALS)
    assert CHECK_NAMES[0] in problems(checks)


def test_the_audit_catches_a_caret_read_as_power():
    checks = audit(swapped("2^3", legacy="8"), REFUSALS)
    assert CHECK_NAMES[1] in problems(checks)


def test_the_audit_catches_a_division_by_zero_answered_with_zero():
    checks = audit(swapped("10/0", shown="0"), REFUSALS)
    assert CHECK_NAMES[2] in problems(checks)


def test_the_audit_catches_the_half_even_answer():
    checks = audit(swapped("2.675", legacy="2.68"), REFUSALS)
    assert CHECK_NAMES[3] in problems(checks)


def test_the_audit_catches_addition_done_first():
    checks = audit(swapped("2+3*4", shown="20"), REFUSALS)
    assert CHECK_NAMES[4] in problems(checks)


def test_the_audit_catches_power_read_left_to_right():
    checks = audit(swapped("2^3^2", shown="64"), REFUSALS)
    assert CHECK_NAMES[5] in problems(checks)


def test_the_audit_catches_unary_minus_binding_tighter_than_power():
    checks = audit(swapped("-2^2", shown="4"), REFUSALS)
    assert CHECK_NAMES[6] in problems(checks)


def test_the_audit_catches_brackets_ignored():
    checks = audit(swapped("(2+3)*4", shown="14"), REFUSALS)
    assert CHECK_NAMES[7] in problems(checks)


def test_the_audit_catches_a_wide_result_printed_anyway():
    wide = tuple((expression, "9.899e+15") if "9999" in expression
                 else (expression, note) for expression, note in REFUSALS)
    checks = audit(ROWS, wide)
    assert CHECK_NAMES[8] in problems(checks)


def test_the_audit_catches_two_rows_for_one_expression():
    checks = audit(ROWS + (ROWS[0],), REFUSALS)
    assert CHECK_NAMES[9] in problems(checks)


def test_the_audit_catches_a_display_that_rounded_down():
    checks = audit(swapped("2.675", shown="2.67"), REFUSALS)
    assert CHECK_NAMES[10] in problems(checks)


def test_every_check_has_a_negative_control():
    """Eleven broken inputs, and every check is named by at least one of them."""
    wide = tuple((expression, "9.899e+15") if "9999" in expression
                 else (expression, note) for expression, note in REFUSALS)
    caught = set()
    caught |= set(problems(audit(swapped("0.1+0.2", legacy="0.3"), REFUSALS)))
    caught |= set(problems(audit(swapped("2^3", legacy="8"), REFUSALS)))
    caught |= set(problems(audit(swapped("10/0", shown="0"), REFUSALS)))
    caught |= set(problems(audit(swapped("2.675", legacy="2.68"), REFUSALS)))
    caught |= set(problems(audit(swapped("2+3*4", shown="20"), REFUSALS)))
    caught |= set(problems(audit(swapped("2^3^2", shown="64"), REFUSALS)))
    caught |= set(problems(audit(swapped("-2^2", shown="4"), REFUSALS)))
    caught |= set(problems(audit(swapped("(2+3)*4", shown="14"), REFUSALS)))
    caught |= set(problems(audit(ROWS, wide)))
    caught |= set(problems(audit(ROWS + (ROWS[0],), REFUSALS)))
    caught |= set(problems(audit(swapped("2.675", shown="2.67"), REFUSALS)))
    assert caught == set(CHECK_NAMES)


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


def test_demo_shows_the_legacy_source(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "CALCULATOR LAB" in out and "return eval(expression)" in out


def test_demo_shows_the_two_answers_for_the_caret(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "eval('2 ^ 3')  -> 1  (xor)" in out
    assert "2 ^ 3') -> 8  (power)" in out


def test_demo_shows_all_eleven_checks(capsys):
    run_demo()
    assert "11/11 checks pass" in capsys.readouterr().out


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


def test_cli_lists_every_expression(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert len(out.strip().splitlines()) == len(EXPRESSIONS)
    assert "0.3" in out


def test_cli_one_expression(capsys):
    assert cli.main(["--expression", "2+2"]) == 0
    assert capsys.readouterr().out.strip().endswith("4")


def test_cli_legacy_column(capsys):
    assert cli.main(["--expression", "2^3", "--legacy"]) == 0
    out = capsys.readouterr().out
    assert "eval=1" in out and "shows=8" in out


def test_cli_tokens(capsys):
    assert cli.main(["--expression", "1+2", "--tokens"]) == 0
    out = capsys.readouterr().out
    assert "number   '1' at 0" in out and "operator '+' at 1" in out


def test_cli_places(capsys):
    assert cli.main(["--expression", "1/3", "--places", "4"]) == 0
    assert "0.3333" in capsys.readouterr().out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 11 and "FAIL" not in out


def test_cli_one_expression_cannot_satisfy_the_audit(capsys):
    assert cli.main(["--expression", "2+2", "--audit"]) == 1
    out, err = capsys.readouterr()
    assert "FAIL" in out and "check(s) failed" in err


def test_cli_writes_the_results_as_json(tmp_path, capsys):
    target = tmp_path / "results.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload["results"]) == len(EXPRESSIONS)
    assert payload["cross_check"]["divide_half_up_2675_1000"] == 268
    assert payload["cross_check"]["decimal_2_675"] == "2.68"
    assert payload["cross_check"]["float_round_2_675"] == 2.67
    assert payload["cross_check"]["legacy_two_caret_three"] == 1
    assert payload["cross_check"]["power_two_cubed"] == "8"
    assert len(payload["refusals"]) == 3


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_refuses_a_missing_bundle(tmp_path, capsys):
    assert cli.main(["--expressions", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_refuses_a_bundle_with_a_hash_comment(tmp_path, capsys):
    path = tmp_path / "expressions.txt"
    path.write_bytes(b"# note\n2+2\n")
    assert cli.main(["--expressions", str(path)]) == 2
    assert "comment starts with ';'" in capsys.readouterr().err


def test_cli_refuses_an_empty_expression(capsys):
    assert cli.main(["--expression", "   "]) == 2
    assert "at least one expression" in capsys.readouterr().err


def test_cli_refuses_too_many_places(capsys):
    assert cli.main(["--places", "13"]) == 2
    assert "between 0 and 12" in capsys.readouterr().err


def test_the_module_keeps_its_place_count_constant():
    assert module.PLACES == 2 and module.MAX_INTEGER_DIGITS == 12
