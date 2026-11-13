"""A small expression calculator: tokenizer, shunting-yard, RPN evaluator.

The pipeline is the classic one:

    "2 + 3 * (4 - 1)"  ->  tokens  ->  RPN  ->  value (11)

Grammar supported
-----------------
- numbers, including decimals (``3.5``) and exponent form (``1e-3``)
- binary ``+ - * / % ^`` with the usual precedence, ``^`` right-associative
- unary ``-`` and ``+`` (``-2^2`` is ``-4``, ``(-2)^2`` is ``4``)
- parentheses
- functions of one or more arguments: ``sqrt``, ``abs``, ``min``, ``max``,
  ``pow``, ``round``, ``log``, ``exp``
- constants ``pi`` and ``e``

Errors are deliberate: an unknown name, a mismatched bracket, a call with the
wrong number of arguments, ``sqrt`` of a negative number and division by zero
all raise ``CalculatorError`` with a message that names the problem.

Fully offline: expressions in, numbers out, no eval(), no network.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

NUMBER = "number"
NAME = "name"
FUNCTION = "function"          # internal stack marker, never a token kind
OPERATOR = "operator"
LPAREN = "("
RPAREN = ")"
COMMA = ","

# operator -> (precedence, right_associative, arity)
OPERATORS = {
    "+": (1, False, 2),
    "-": (1, False, 2),
    "*": (2, False, 2),
    "/": (2, False, 2),
    "%": (2, False, 2),
    "u-": (3, True, 1),
    "u+": (3, True, 1),
    "^": (4, True, 2),
}

FUNCTIONS = {
    "sqrt": (1, math.sqrt),
    "abs": (1, abs),
    "round": (1, round),
    "log": (1, math.log),
    "exp": (1, math.exp),
    "min": (2, min),
    "max": (2, max),
    "pow": (2, pow),
}

CONSTANTS = {"pi": math.pi, "e": math.e}

MAX_LENGTH = 200

_TOKEN_RE = re.compile(
    r"\s*(?:(?P<number>(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)"
    r"|(?P<name>[A-Za-z_][A-Za-z_0-9]*)"
    r"|(?P<op>[-+*/%^(),]))"
)

SPELLED = {
    "*": "times", "/": "divide", "-": "minus", "+": "plus",
    "^": "power", "%": "mod", "(": "(", ")": ")", ",": ",",
}


class CalculatorError(ValueError):
    """Every failure mode of the calculator, with a human-readable message."""


@dataclass(frozen=True)
class Token:
    kind: str
    text: str

    def __str__(self) -> str:              # pragma: no cover - display only
        return self.text


# --------------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------------- #
def tokenize(expression: str) -> list[Token]:
    """Split an expression into tokens, rejecting anything unrecognised."""
    if not isinstance(expression, str):
        raise CalculatorError("expression must be a string")
    text = expression.strip()
    if not text:
        raise CalculatorError("expression is empty")
    if len(text) > MAX_LENGTH:
        raise CalculatorError(f"expression is longer than {MAX_LENGTH} chars")

    tokens: list[Token] = []
    position = 0
    while position < len(text):
        match = _TOKEN_RE.match(text, position)
        if not match:
            raise CalculatorError(
                f"unexpected character {text[position]!r} at position "
                f"{position}")
        position = match.end()
        if match.group("number") is not None:
            tokens.append(Token(NUMBER, match.group("number")))
        elif match.group("name") is not None:
            tokens.append(Token(NAME, match.group("name")))
        else:
            symbol = match.group("op")
            kind = {LPAREN: LPAREN, RPAREN: RPAREN, COMMA: COMMA}.get(
                symbol, OPERATOR)
            tokens.append(Token(kind, symbol))
    if not tokens:
        raise CalculatorError("expression is empty")
    return tokens


# --------------------------------------------------------------------------- #
# Shunting-yard
# --------------------------------------------------------------------------- #
def to_rpn(tokens: Sequence[Token]) -> list[Token]:
    """Convert infix tokens to reverse polish notation.

    A stack of operators plus one *frame* per open parenthesis keeps track of
    argument counts, so a function call can be checked for arity as soon as it
    closes. A function name is pushed as a ``FUNCTION`` marker: it is not an
    operator and never reaches the output until its parenthesis closes.
    """
    output: list[Token] = []
    stack: list[Token] = []
    frames: list[dict[str, object]] = []     # one per open parenthesis
    previous: Token | None = None

    for token in tokens:
        if token.kind == NUMBER:
            _expect_operator(previous, token)
            output.append(token)
            _mark_value(frames)
        elif token.kind == NAME:
            if token.text in CONSTANTS:
                _expect_operator(previous, token)
                output.append(token)
                _mark_value(frames)
            elif token.text in FUNCTIONS:
                _expect_operator(previous, token)
                stack.append(Token(FUNCTION, token.text))
            else:
                raise CalculatorError(f"unknown name {token.text!r}")
        elif token.kind == LPAREN:
            if _is_value(previous):
                raise CalculatorError("missing operator before '('")
            is_call = bool(stack and stack[-1].kind == FUNCTION)
            stack.append(token)
            frames.append({"count": 0, "has_value": False, "is_call": is_call})
        elif token.kind == COMMA:
            if not frames:
                raise CalculatorError("misplaced comma")
            while stack and stack[-1].kind != LPAREN:
                output.append(stack.pop())
            if not stack or stack[-1].kind != LPAREN:
                raise CalculatorError("misplaced comma")
            frame = frames[-1]
            if not frame["has_value"]:
                raise CalculatorError("misplaced comma")
            frame["count"] = int(frame["count"]) + 1     # type: ignore[arg-type]
            frame["has_value"] = False
        elif token.kind == RPAREN:
            while stack and stack[-1].kind not in (LPAREN, FUNCTION):
                output.append(stack.pop())
            if not stack:
                raise CalculatorError("unbalanced ')'")
            stack.pop()                       # the matching LPAREN
            frame = frames.pop() if frames else {
                "count": 0, "has_value": True, "is_call": True}
            arguments = int(frame["count"]) + (1 if frame["has_value"] else 0)
            if not frame["is_call"]:
                if int(frame["count"]) > 0:
                    raise CalculatorError("misplaced comma")
                if not frame["has_value"]:
                    raise CalculatorError("empty parentheses")
            elif stack and stack[-1].kind == FUNCTION:
                function = stack.pop()
                arity = FUNCTIONS[function.text][0]
                if arguments != arity:
                    raise CalculatorError(
                        f"{function.text}() takes {arity} argument(s), "
                        f"got {arguments}")
                output.append(Token(NAME, function.text))
            _mark_value(frames)               # a group or call is a value
        else:                                   # an operator
            symbol = token.text
            if symbol in "+-" and not _is_value(previous):
                symbol = "u" + symbol            # unary
            if not symbol.startswith("u") and not _is_value(previous):
                raise CalculatorError(
                    f"operator {token.text!r} is missing an operand")
            precedence, right, _arity = OPERATORS[symbol]
            while stack and stack[-1].kind == OPERATOR:
                top_prec = OPERATORS[stack[-1].text][0]
                if top_prec > precedence or (top_prec == precedence
                                             and not right):
                    output.append(stack.pop())
                else:
                    break
            stack.append(Token(OPERATOR, symbol))
        previous = token

    while stack:
        top = stack.pop()
        if top.kind == LPAREN:
            raise CalculatorError("unbalanced '('")
        if top.kind == FUNCTION:
            raise CalculatorError(f"{top.text}() used without parentheses")
        output.append(top)
    return output


def _is_value(previous: Token | None) -> bool:
    """True when the previous token can end a value (a number, constant, ')')."""
    if previous is None:
        return False
    if previous.kind == NAME:
        return previous.text in CONSTANTS
    return previous.kind in (NUMBER, RPAREN)


def _expect_operator(previous: Token | None, token: Token) -> None:
    """A number or constant may not follow another value without an operator."""
    if previous is None:
        return
    if previous.kind == NAME and previous.text in FUNCTIONS:
        raise CalculatorError(f"{previous.text}() used without parentheses")
    if _is_value(previous):
        raise CalculatorError(f"missing operator before {token.text!r}")


def _mark_value(frames: list[dict[str, object]]) -> None:
    if frames:
        frames[-1]["has_value"] = True


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
def evaluate_rpn(rpn: Sequence[Token]) -> float:
    stack: list[float] = []
    for token in rpn:
        if token.kind == NUMBER:
            stack.append(float(token.text))
        elif token.kind == NAME and token.text in CONSTANTS:
            stack.append(CONSTANTS[token.text])
        elif token.kind == NAME:
            arity, function = FUNCTIONS[token.text]
            if len(stack) < arity:
                raise CalculatorError(
                    f"{token.text}() needs {arity} argument(s)")
            arguments = [stack.pop() for _ in range(arity)][::-1]
            try:
                stack.append(function(*arguments))
            except (ValueError, ZeroDivisionError) as exc:
                raise CalculatorError(
                    f"{token.text}({', '.join(_fmt(a) for a in arguments)}) "
                    f"failed: {exc}") from exc
        else:
            _arity = OPERATORS[token.text][2]
            if len(stack) < _arity:
                raise CalculatorError(
                    f"operator {token.text!r} is missing an operand")
            if _arity == 1:
                value = stack.pop()
                stack.append(-value if token.text == "u-" else +value)
            else:
                right = stack.pop()
                left = stack.pop()
                stack.append(_apply(token.text, left, right))
    if len(stack) != 1:
        raise CalculatorError("expression does not reduce to a single value")
    return stack[0]


def _apply(operator: str, left: float, right: float) -> float:
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    if operator == "/":
        if right == 0:
            raise CalculatorError("division by zero")
        return left / right
    if operator == "%":
        if right == 0:
            raise CalculatorError("modulo by zero")
        return math.fmod(left, right)
    if operator == "^":
        try:
            return float(left ** right)
        except (OverflowError, ValueError, TypeError) as exc:
            raise CalculatorError(f"cannot raise {left} to {right}") from exc
    raise CalculatorError(f"unknown operator {operator!r}")


def evaluate(expression: str) -> float:
    """Tokenize, convert and evaluate in one call."""
    return evaluate_rpn(to_rpn(tokenize(expression)))


def _fmt(value: float) -> str:
    return f"{value:g}"


def format_value(value: float) -> str:
    """Render a result without floating-point noise and without exponents."""
    if value != value or value in (float("inf"), float("-inf")):
        raise CalculatorError("result is not a finite number")
    rounded = round(value, 10)
    if rounded == int(rounded) and abs(rounded) < 1e15:
        return str(int(rounded))
    return f"{rounded:.10f}".rstrip("0").rstrip(".")


# --------------------------------------------------------------------------- #
# Session with history
# --------------------------------------------------------------------------- #
@dataclass
class Calculator:
    """A calculator that remembers what it evaluated, and can undo."""

    history: list[tuple[str, float]] = field(default_factory=list)

    def evaluate(self, expression: str) -> float:
        value = evaluate(expression)
        self.history.append((expression.strip(), value))
        return value

    def last(self) -> tuple[str, float] | None:
        return self.history[-1] if self.history else None

    def undo(self) -> tuple[str, float] | None:
        return self.history.pop() if self.history else None

    def clear(self) -> None:
        self.history.clear()

    def total(self) -> float:
        return sum(value for _expression, value in self.history)

    def __len__(self) -> int:
        return len(self.history)


def evaluate_lines(lines: Iterable[str]) -> tuple[list[tuple[str, float]],
                                                 list[tuple[str, str]]]:
    """Evaluate many expressions, returning successes and failures separately.

    Blank lines and lines starting with ``#`` are ignored, so the bundled
    file can carry comments. A failing line never aborts the batch.
    """
    results: list[tuple[str, float]] = []
    failures: list[tuple[str, str]] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            results.append((line, evaluate(line)))
        except CalculatorError as exc:
            failures.append((line, str(exc)))
    return results, failures


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
EXPECTED_DEMO_CASES = (
    ("2 + 3 * 4", 14.0),
    ("(2 + 3) * 4", 20.0),
    ("2 ^ 3 ^ 2", 512.0),
    ("-2 ^ 2", -4.0),
    ("(-2) ^ 2", 4.0),
    ("10 / 4", 2.5),
    ("sqrt(16) + abs(-3)", 7.0),
    ("max(2, 7) - min(2, 7)", 5.0),
    ("round(pi * 100) / 100", 3.14),
    ("7 % 4", 3.0),
)


def run_demo() -> int:
    print("=" * 66)
    print(" CALCULATOR - tokenizer, shunting-yard, RPN evaluation")
    print(" Precedence, parentheses, unary minus, functions, history.")
    print("=" * 66)

    # 1. the documented cases evaluate to the documented numbers
    for expression, expected in EXPECTED_DEMO_CASES:
        actual = evaluate(expression)
        assert abs(actual - expected) < 1e-9, (expression, actual, expected)
        print(f"  {expression:<24} = {format_value(actual)}")

    # 2. tokenizer shape: numbers, names and operators are distinct
    tokens = tokenize("max(2, 7) - 1")
    assert [token.kind for token in tokens] == [
        NAME, LPAREN, NUMBER, COMMA, NUMBER, RPAREN, OPERATOR, NUMBER]
    assert [token.text for token in tokens] == [
        "max", "(", "2", ",", "7", ")", "-", "1"]

    # 3. RPN output is the documented postfix form
    assert [token.text for token in to_rpn(tokenize("2 + 3 * 4"))] == \
        ["2", "3", "4", "*", "+"]
    assert [token.text for token in to_rpn(tokenize("(2 + 3) * 4"))] == \
        ["2", "3", "+", "4", "*"]

    # 4. negative control: a broken bracket, an unknown name and a bad arity
    for bad, message in (
        ("(2 + 3", "unbalanced '('"),
        ("2 + 3)", "unbalanced ')'"),
        ("foo(1)", "unknown name"),
        ("max(1)", "takes 2 argument"),
        ("2 +", "missing an operand"),
        ("2 3", "missing operator"),
        ("", "empty"),
    ):
        try:
            evaluate(bad)
        except CalculatorError as exc:
            assert message in str(exc), (bad, str(exc))
        else:
            raise AssertionError(f"{bad!r} should have failed")

    # 5. division by zero is an error, not infinity
    try:
        evaluate("1 / 0")
    except CalculatorError as exc:
        assert "division by zero" in str(exc)
    else:
        raise AssertionError("1 / 0 should fail")

    # 6. history: evaluate, undo, clear, total
    calc = Calculator()
    calc.evaluate("1 + 1")
    calc.evaluate("2 * 3")
    assert len(calc) == 2
    assert calc.last() == ("2 * 3", 6.0)
    assert calc.total() == 8.0
    assert calc.undo() == ("2 * 3", 6.0)
    assert len(calc) == 1
    calc.clear()
    assert len(calc) == 0 and calc.undo() is None

    # 7. batch evaluation keeps going after a bad line
    results, failures = evaluate_lines([
        "1 + 1", "# a comment", "", "bogus(", "sqrt(9)"])
    assert [value for _text, value in results] == [2.0, 3.0]
    assert len(failures) == 1 and failures[0][0] == "bogus("

    # 8. formatting never leaks float noise
    assert format_value(0.1 + 0.2) == "0.3"
    assert format_value(14.0) == "14"
    assert format_value(-2.5) == "-2.5"

    # 9. determinism: the same expression always gives the same value
    assert evaluate("sqrt(2) ^ 2") == evaluate("sqrt(2) ^ 2")

    print()
    print(f"Cross-checks OK: {len(EXPECTED_DEMO_CASES)} documented "
          f"expressions, {len(to_rpn(tokenize('2 + 3 * 4')))}-token RPN, "
          f"token kinds split, 7 malformed expressions rejected, division "
          f"by zero refused, history undo/clear, batch survives a bad line, "
          f"float noise removed, deterministic re-evaluation")
    print("\nDemo completed successfully.")
    return 0
