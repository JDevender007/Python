"""Tests for Calculator_CLI: tokenizer, parser, evaluator, session and CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import calculator                                        # noqa: E402
import main as cli                                       # noqa: E402
from calculator import (                                 # noqa: E402
    CONSTANTS,
    FUNCTIONS,
    NAME,
    NUMBER,
    OPERATOR,
    RPAREN,
    LPAREN,
    COMMA,
    Calculator,
    CalculatorError,
    Token,
    evaluate,
    evaluate_lines,
    format_value,
    to_rpn,
    tokenize,
)


# --------------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------------- #
def test_tokenize_numbers_and_operators():
    tokens = tokenize("1+2")
    assert [t.kind for t in tokens] == [NUMBER, OPERATOR, NUMBER]
    assert [t.text for t in tokens] == ["1", "+", "2"]


def test_tokenize_ignores_whitespace():
    assert tokenize("  1   +   2  ") == tokenize("1+2")


def test_tokenize_decimals():
    assert [t.text for t in tokenize("3.5 + .25")] == ["3.5", "+", ".25"]


def test_tokenize_exponent_form():
    assert [t.text for t in tokenize("1e-3")] == ["1e-3"]


def test_tokenize_names_and_calls():
    kinds = [t.kind for t in tokenize("max(2, 7)")]
    assert kinds == [NAME, LPAREN, NUMBER, COMMA, NUMBER, RPAREN]


def test_tokenize_all_operator_symbols():
    assert [t.text for t in tokenize("+-*/%^")] == ["+", "-", "*", "/", "%", "^"]


def test_tokenize_rejects_unknown_character():
    with pytest.raises(CalculatorError, match="unexpected character"):
        tokenize("2 & 3")


def test_tokenize_rejects_empty():
    with pytest.raises(CalculatorError, match="empty"):
        tokenize("   ")


def test_tokenize_rejects_too_long():
    with pytest.raises(CalculatorError, match="longer than"):
        tokenize("1" * (calculator.MAX_LENGTH + 1))


def test_tokenize_rejects_non_string():
    with pytest.raises(CalculatorError, match="must be a string"):
        tokenize(123)                                        # type: ignore[arg-type]


def test_token_str_is_the_text():
    assert str(Token(NUMBER, "42")) == "42"


# --------------------------------------------------------------------------- #
# Shunting-yard
# --------------------------------------------------------------------------- #
def _rpn(expression: str) -> list[str]:
    return [t.text for t in to_rpn(tokenize(expression))]


def test_rpn_simple():
    assert _rpn("2 + 3 * 4") == ["2", "3", "4", "*", "+"]


def test_rpn_parentheses():
    assert _rpn("(2 + 3) * 4") == ["2", "3", "+", "4", "*"]


def test_rpn_power_is_right_associative():
    assert _rpn("2 ^ 3 ^ 2") == ["2", "3", "2", "^", "^"]


def test_rpn_subtraction_is_left_associative():
    assert _rpn("10 - 3 - 2") == ["10", "3", "-", "2", "-"]


def test_rpn_unary_minus_is_marked():
    assert _rpn("-3") == ["3", "u-"]


def test_rpn_unary_plus_is_marked():
    assert _rpn("+3") == ["3", "u+"]


def test_rpn_double_unary():
    assert _rpn("--3") == ["3", "u-", "u-"]


def test_rpn_function_call_keeps_arity():
    assert _rpn("sqrt(9)") == ["9", "sqrt"]


def test_rpn_two_argument_function():
    assert _rpn("max(1, 2)") == ["1", "2", "max"]


def test_rpn_nested_calls():
    assert _rpn("abs(abs(5))") == ["5", "abs", "abs"]


def test_rpn_constant_is_a_value():
    assert _rpn("pi") == ["pi"]


def test_rpn_rejects_unbalanced_open():
    with pytest.raises(CalculatorError, match=r"unbalanced '\('"):
        to_rpn(tokenize("(1 + 2"))


def test_rpn_rejects_unbalanced_close():
    with pytest.raises(CalculatorError, match=r"unbalanced '\)'"):
        to_rpn(tokenize("1 + 2)"))


def test_rpn_rejects_unknown_name():
    with pytest.raises(CalculatorError, match="unknown name"):
        to_rpn(tokenize("foo(1)"))


def test_rpn_rejects_wrong_arity():
    with pytest.raises(CalculatorError, match="takes 2 argument"):
        to_rpn(tokenize("max(1)"))


def test_rpn_rejects_function_without_parentheses():
    with pytest.raises(CalculatorError, match="without parentheses"):
        to_rpn(tokenize("sqrt 4"))


def test_rpn_rejects_missing_operator_between_numbers():
    with pytest.raises(CalculatorError, match="missing operator"):
        to_rpn(tokenize("2 3"))


def test_rpn_rejects_missing_operator_before_paren():
    with pytest.raises(CalculatorError, match="missing operator"):
        to_rpn(tokenize("2(3)"))


def test_rpn_rejects_leading_binary_operator():
    with pytest.raises(CalculatorError, match="missing an operand"):
        to_rpn(tokenize("* 2"))


def test_rpn_rejects_misplaced_comma_at_top_level():
    with pytest.raises(CalculatorError, match="misplaced comma"):
        to_rpn(tokenize("1, 2"))


def test_rpn_rejects_comma_in_plain_parentheses():
    with pytest.raises(CalculatorError, match="misplaced comma"):
        to_rpn(tokenize("(1, 2)"))


def test_rpn_rejects_empty_parentheses():
    with pytest.raises(CalculatorError, match="empty parentheses"):
        to_rpn(tokenize("()"))


def test_rpn_rejects_zero_argument_call():
    with pytest.raises(CalculatorError, match="got 0"):
        to_rpn(tokenize("sqrt()"))


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("expression, expected", [
    ("1 + 2", 3.0),
    ("7 - 10", -3.0),
    ("6 * 7", 42.0),
    ("7 / 2", 3.5),
    ("2 ^ 10", 1024.0),
    ("7 % 4", 3.0),
    ("-3", -3.0),
    ("+3", 3.0),
    ("2 + 3 * 4", 14.0),
    ("(2 + 3) * 4", 20.0),
    ("2 ^ 3 ^ 2", 512.0),
    ("-2 ^ 2", -4.0),
    ("(-2) ^ 2", 4.0),
    ("10 - 3 - 2", 5.0),
    ("100 / 5 / 2", 10.0),
    ("2 * -3", -6.0),
    ("-2 * 3", -6.0),
    ("2 - -3", 5.0),
    ("1e-3 * 1000", 1.0),
])
def test_evaluate_arithmetic(expression, expected):
    assert evaluate(expression) == pytest.approx(expected)


def test_evaluate_constants():
    assert evaluate("pi") == pytest.approx(3.141592653589793)
    assert evaluate("e") == pytest.approx(2.718281828459045)


def test_evaluate_round_constant():
    assert evaluate("round(pi * 100) / 100") == pytest.approx(3.14)


@pytest.mark.parametrize("expression, expected", [
    ("sqrt(16)", 4.0),
    ("abs(-3)", 3.0),
    ("log(e)", 1.0),
    ("exp(0)", 1.0),
    ("round(2.6)", 3.0),
    ("min(4, 9)", 4.0),
    ("max(4, 9)", 9.0),
    ("pow(2, 5)", 32.0),
])
def test_evaluate_functions(expression, expected):
    assert evaluate(expression) == pytest.approx(expected)


def test_evaluate_nested_functions():
    assert evaluate("abs(abs(-5))") == 5.0
    assert evaluate("max(min(1, 2), 3)") == 3.0


def test_evaluate_division_by_zero():
    with pytest.raises(CalculatorError, match="division by zero"):
        evaluate("1 / 0")


def test_evaluate_modulo_by_zero():
    with pytest.raises(CalculatorError, match="modulo by zero"):
        evaluate("1 % 0")


def test_evaluate_sqrt_of_negative_reports_function():
    with pytest.raises(CalculatorError, match="sqrt"):
        evaluate("sqrt(-1)")


def test_evaluate_log_of_zero_reports_function():
    with pytest.raises(CalculatorError, match="log"):
        evaluate("log(0)")


def test_evaluate_complex_power_is_an_error():
    with pytest.raises(CalculatorError, match="cannot raise"):
        evaluate("(-2) ^ 0.5")


def test_evaluate_overflowing_power_is_an_error():
    with pytest.raises(CalculatorError, match="cannot raise"):
        evaluate("10 ^ 400")


def test_function_table_matches_documented_arities():
    assert FUNCTIONS["sqrt"][0] == 1
    assert FUNCTIONS["min"][0] == 2
    assert set(CONSTANTS) == {"pi", "e"}


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
def test_format_value_removes_float_noise():
    assert format_value(0.1 + 0.2) == "0.3"


def test_format_value_integers():
    assert format_value(14.0) == "14"
    assert format_value(-4.0) == "-4"


def test_format_value_keeps_decimals():
    assert format_value(2.5) == "2.5"
    assert format_value(1 / 3) == "0.3333333333"


def test_format_value_rejects_infinity():
    with pytest.raises(CalculatorError, match="not a finite number"):
        format_value(float("inf"))


def test_format_value_rejects_nan():
    with pytest.raises(CalculatorError, match="not a finite number"):
        format_value(float("nan"))


# --------------------------------------------------------------------------- #
# Session / history
# --------------------------------------------------------------------------- #
def test_history_records_expressions():
    calc = Calculator()
    assert calc.evaluate("1 + 1") == 2.0
    assert calc.evaluate("2 * 3") == 6.0
    assert len(calc) == 2
    assert calc.last() == ("2 * 3", 6.0)


def test_history_is_empty_initially():
    calc = Calculator()
    assert len(calc) == 0
    assert calc.last() is None
    assert calc.undo() is None


def test_history_total_sums_values():
    calc = Calculator()
    calc.evaluate("1 + 1")
    calc.evaluate("2 * 3")
    assert calc.total() == 8.0


def test_history_undo_removes_last_entry():
    calc = Calculator()
    calc.evaluate("1 + 1")
    calc.evaluate("2 * 3")
    assert calc.undo() == ("2 * 3", 6.0)
    assert len(calc) == 1
    assert calc.last() == ("1 + 1", 2.0)


def test_history_clear():
    calc = Calculator()
    calc.evaluate("1 + 1")
    calc.clear()
    assert len(calc) == 0
    assert calc.total() == 0.0


def test_failed_expression_is_not_recorded():
    calc = Calculator()
    with pytest.raises(CalculatorError):
        calc.evaluate("1 / 0")
    assert len(calc) == 0


# --------------------------------------------------------------------------- #
# Batch evaluation
# --------------------------------------------------------------------------- #
def test_evaluate_lines_collapses_batch():
    results, failures = evaluate_lines(["1 + 1", "sqrt(9)"])
    assert results == [("1 + 1", 2.0), ("sqrt(9)", 3.0)]
    assert failures == []


def test_evaluate_lines_skips_comments_and_blank_lines():
    results, failures = evaluate_lines(["# note", "", "   ", "2 + 2"])
    assert results == [("2 + 2", 4.0)]
    assert failures == []


def test_evaluate_lines_keeps_going_after_a_failure():
    results, failures = evaluate_lines(["1 + 1", "bogus(", "2 + 2"])
    assert [text for text, _ in results] == ["1 + 1", "2 + 2"]
    assert len(failures) == 1
    assert failures[0][0] == "bogus("
    assert "unknown name" in failures[0][1]


# --------------------------------------------------------------------------- #
# Bundled data
# --------------------------------------------------------------------------- #
def test_bundled_file_has_one_deliberate_failure():
    lines = (PROJECT / "data" / "expressions.txt").read_text(
        encoding="utf-8").splitlines()
    results, failures = evaluate_lines(lines)
    assert len(results) >= 15
    assert [text for text, _ in failures] == ["max(1)"]


def test_bundled_file_results_are_finite():
    lines = (PROJECT / "data" / "expressions.txt").read_text(
        encoding="utf-8").splitlines()
    results, _failures = evaluate_lines(lines)
    for _text, value in results:
        assert value == value and abs(value) != float("inf")


# --------------------------------------------------------------------------- #
# Library demo
# --------------------------------------------------------------------------- #
def test_run_demo_returns_zero(capsys):
    assert calculator.run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_run_demo_is_deterministic(capsys):
    calculator.run_demo()
    first = capsys.readouterr().out
    calculator.run_demo()
    second = capsys.readouterr().out
    assert first == second


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert cli.main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "CALCULATOR CLI" in out
    assert "Demo completed successfully." in out


def test_cli_demo_quiet_prints_nothing(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_single_expression(capsys):
    assert cli.main(["--expr", "2 + 3 * 4"]) == 0
    out = capsys.readouterr().out
    assert "2 + 3 * 4" in out
    assert "= 14" in out


def test_cli_multiple_expressions(capsys):
    assert cli.main(["--expr", "1 + 1", "--expr", "sqrt(9)"]) == 0
    out = capsys.readouterr().out
    assert "= 2" in out
    assert "= 3" in out
    assert "2 evaluated, 0 failed" in out


def test_cli_bad_expression_exits_two(capsys):
    assert cli.main(["--expr", "1 +"]) == 2
    out = capsys.readouterr().out
    assert "1 failed" in out


def test_cli_file_mode(tmp_path, capsys):
    path = tmp_path / "exprs.txt"
    path.write_text("# comment\n4 * 5\n\n", encoding="utf-8")
    assert cli.main(["--file", str(path)]) == 0
    assert "= 20" in capsys.readouterr().out


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "no-such-file.txt"]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_default_file_is_the_bundled_one(capsys):
    assert cli.main([]) == 2                    # the file has one broken line
    out = capsys.readouterr().out
    assert "1 failed" in out


def test_cli_json_output(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--expr", "6 * 7", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["results"] == [{"expression": "6 * 7", "value": 42.0}]
    assert payload["failures"] == []


def test_cli_json_records_failures(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--expr", "max(1)", "--json", str(target)]) == 2
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["results"] == []
    assert payload["failures"][0]["expression"] == "max(1)"
    assert "takes 2 argument" in payload["failures"][0]["error"]


def test_cli_quiet_expression_prints_nothing(capsys):
    assert cli.main(["--expr", "1 + 1", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
