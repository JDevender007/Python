"""A calculator's display is not a number, and `eval` is not a calculator.

The legacy calculator was two lines:

    def calculate(expression):
        return eval(expression)

and a window that pasted the answer into a label. **1. `eval` evaluates Python, not
arithmetic.** So `2 ^ 3` is `1` -- XOR -- where every calculator on earth says `8`, and a
typed expression can call any function in scope.

**2. A float is not a decimal.** `0.1 + 0.2` is `0.30000000000000004`, and the label that
shows it is the only place the error is visible. `round(2.675, 2)` is `2.67`, because the
nearest double is below the tie and Python rounds the *double*, not the decimal.

**3. `1 / 0` raises, and `1 / 3` never ends.** The first kills the click handler; the second
prints seventeen digits that the next click will multiply by.

**4. A display has a width.** A number with more digits than the label holds is printed as
`1.2345678901234567e+19`, which is not a number anyone can read back.

So this module evaluates the expression itself: a tokenizer that knows numbers and six
operators, a recursive-descent parser with real precedence, `Decimal` arithmetic at 34
digits, and a `render` that rounds half-up to a stated number of places and refuses a result
that will not fit. The legacy path is kept beside it, executable, so every claim above is
reproduced with a number.

The demonstration is offline: one bundled file of expressions. Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import (Decimal, DecimalException, InvalidOperation, ROUND_HALF_UP,
                     localcontext)
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EXPRESSIONS_FILE = DATA_DIR / "expressions.txt"

#: The legacy calculator, transcribed -- and executable.
LEGACY_CALCULATE = ("def calculate(expression):\n"
                    "    return eval(expression)")

#: The characters a number may hold.
DIGITS = "0123456789"

#: The operators, longest first is irrelevant here (all are one character).
OPERATORS = ("+", "-", "*", "/", "%", "^")

#: How many digits of working precision the calculator keeps.
WORKING_DIGITS = 34

#: How many digits a display may show before the point.
MAX_INTEGER_DIGITS = 12

#: How deep parentheses may nest before the parser refuses.
MAX_DEPTH = 32

#: How many decimal places the default display rounds to.
PLACES = 2


class CalcError(Exception):
    """An expression that cannot be read, or a result that cannot be shown."""


# --------------------------------------------------------------------------- #
# Tokens
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Token:
    """One number, one operator, or one bracket, at the place it was found."""

    kind: str
    text: str
    at: int

    def __post_init__(self) -> None:
        if self.kind not in ("number", "operator", "open", "close"):
            raise CalcError(f"{self.kind!r} is not a token kind")
        if not self.text:
            raise CalcError("a token carries its text")
        if self.at < 0:
            raise CalcError(f"a token is at a position of at least 0, got {self.at}")

    def line(self) -> str:
        return f"{self.kind:<8} {self.text!r} at {self.at}"


def tokenize(text: str) -> tuple[Token, ...]:
    """Split an expression into tokens, refusing anything that is not arithmetic."""
    if not isinstance(text, str):
        raise CalcError(f"an expression is text, got {type(text).__name__}")
    tokens: list[Token] = []
    position = 0
    while position < len(text):
        character = text[position]
        if character.isspace():
            position += 1
            continue
        if character in DIGITS or character == ".":
            start = position
            seen_dot = False
            while position < len(text) and (text[position] in DIGITS
                                            or text[position] == "."):
                if text[position] == ".":
                    if seen_dot:
                        raise CalcError(f"a number holds one decimal point, and "
                                        f"found a second at {position}")
                    seen_dot = True
                position += 1
            body = text[start:position]
            if body == ".":
                raise CalcError(f"a decimal point at {start} needs a digit")
            tokens.append(Token("number", body, start))
            continue
        if character in OPERATORS:
            tokens.append(Token("operator", character, position))
            position += 1
            continue
        if character == "(":
            tokens.append(Token("open", character, position))
            position += 1
            continue
        if character == ")":
            tokens.append(Token("close", character, position))
            position += 1
            continue
        raise CalcError(f"{character!r} at {position} is not part of an "
                        f"expression: only digits, . + - * / % ^ and brackets")
    if not tokens:
        raise CalcError("an expression needs at least one token")
    return tuple(tokens)


# --------------------------------------------------------------------------- #
# The parser
# --------------------------------------------------------------------------- #
class Parser:
    """Recursive descent over the tokens, with the precedence a calculator means.

    expression := term (('+' | '-') term)*
    term       := unary (('*' | '/' | '%') unary)*
    unary      := ('+' | '-') unary | power
    power      := primary ('^' unary)?
    primary    := number | '(' expression ')'

    `power` recurses through `unary` on the right, so `2^3^2` is `2^(3^2)`. `unary`
    sits *above* `power`, so `-2^2` is `-(2^2)`, the way a calculator and Python both
    read it.
    """

    def __init__(self, tokens) -> None:
        held = tuple(tokens)
        if not held:
            raise CalcError("a parser needs at least one token")
        self.tokens = held
        self.position = 0
        self.depth = 0

    # -- plumbing ---------------------------------------------------------- #
    def peek(self) -> Token | None:
        if self.position >= len(self.tokens):
            return None
        return self.tokens[self.position]

    def take(self) -> Token:
        token = self.peek()
        if token is None:
            raise CalcError("the expression ends where a value was expected")
        self.position += 1
        return token

    def accept(self, text: str) -> bool:
        token = self.peek()
        if token is not None and token.kind == "operator" and token.text == text:
            self.position += 1
            return True
        return False

    # -- grammar ----------------------------------------------------------- #
    def parse(self) -> Decimal:
        value = self.expression()
        leftover = self.peek()
        if leftover is not None:
            raise CalcError(f"{leftover.text!r} at {leftover.at} follows a "
                            f"complete expression")
        return value

    def expression(self) -> Decimal:
        value = self.term()
        while True:
            if self.accept("+"):
                value = value + self.term()
            elif self.accept("-"):
                value = value - self.term()
            else:
                return value

    def term(self) -> Decimal:
        value = self.unary()
        while True:
            if self.accept("*"):
                value = value * self.unary()
            elif self.accept("/"):
                divisor = self.unary()
                if divisor == 0:
                    raise CalcError("division by zero has no value, and a "
                                    "calculator must say so")
                value = value / divisor
            elif self.accept("%"):
                divisor = self.unary()
                if divisor == 0:
                    raise CalcError("a remainder by zero has no value")
                value = value % divisor
            else:
                return value

    def unary(self) -> Decimal:
        token = self.peek()
        if token is not None and token.kind == "operator" and token.text in ("+", "-"):
            self.position += 1
            value = self.unary()
            return -value if token.text == "-" else value
        return self.power()

    def power(self) -> Decimal:
        base = self.primary()
        if self.accept("^"):
            exponent = self.unary()
            if exponent != exponent.to_integral_value():
                raise CalcError(f"the exponent {exponent} is not a whole number, "
                                f"and this calculator only raises to whole powers")
            return base ** int(exponent)
        return base

    def primary(self) -> Decimal:
        token = self.take()
        if token.kind == "number":
            try:
                return Decimal(token.text)
            except InvalidOperation as error:
                raise CalcError(f"{token.text!r} at {token.at} is not a number: "
                                f"{error}") from None
        if token.kind == "open":
            self.depth += 1
            if self.depth > MAX_DEPTH:
                raise CalcError(f"brackets nest {MAX_DEPTH} deep at most, and "
                                f"this expression went deeper")
            value = self.expression()
            closing = self.take()
            if closing.kind != "close":
                raise CalcError(f"{closing.text!r} at {closing.at} closes a "
                                f"bracket that was opened at {token.at}")
            self.depth -= 1
            return value
        raise CalcError(f"{token.text!r} at {token.at} is an operator where a "
                        f"number or a bracket was expected")


def evaluate(text: str) -> Decimal:
    """Read one expression and answer its exact value, at 34 working digits."""
    tokens = tokenize(text)
    with localcontext() as context:
        context.prec = WORKING_DIGITS
        try:
            return Parser(tokens).parse()
        except DecimalException as error:
            raise CalcError(f"{text!r} cannot be evaluated: {error}") from None
        except RecursionError:
            raise CalcError(f"{text!r} nests too deeply to evaluate") from None


# --------------------------------------------------------------------------- #
# The display
# --------------------------------------------------------------------------- #
def render(value: Decimal, places: int = PLACES) -> str:
    """Round half-up to `places` and print the digits, or refuse to fit them."""
    if not isinstance(value, Decimal):
        raise CalcError(f"a display shows a Decimal, got {type(value).__name__}")
    if not isinstance(places, int) or isinstance(places, bool):
        raise CalcError(f"places is a whole number, got {places!r}")
    if places < 0 or places > 12:
        raise CalcError(f"places is between 0 and 12, got {places}")
    if value.is_nan() or value.is_infinite():
        raise CalcError("a display cannot show a value that is not finite")
    step = Decimal(1).scaleb(-places)
    with localcontext() as context:
        context.prec = MAX_INTEGER_DIGITS + places + 6
        try:
            rounded = value.quantize(step, rounding=ROUND_HALF_UP)
        except DecimalException:
            raise CalcError(f"the result is wider than a display that holds "
                            f"{MAX_INTEGER_DIGITS} digits before the point") from None
    text = f"{rounded:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("", "-0", "-"):
        text = "0"
    whole = text.lstrip("-").split(".")[0]
    if len(whole) > MAX_INTEGER_DIGITS:
        raise CalcError(f"the result needs {len(whole)} digits before the point, "
                        f"and the display holds {MAX_INTEGER_DIGITS}")
    return text


def exact(value: Decimal) -> str:
    """The value with every digit the working precision kept, for comparison."""
    text = f"{value:f}"
    return text


# --------------------------------------------------------------------------- #
# Half-up on integers, for money
# --------------------------------------------------------------------------- #
def divide_half_up(numerator: int, denominator: int, places: int = 2) -> int:
    """`numerator / denominator` at `places`, rounded half-up, as a whole number.

    The cross-check for `Decimal.quantize`: two routes to the same digits, one of
    which never touches a float or a `round()`.
    """
    for value, name in ((numerator, "a numerator"), (denominator, "a denominator"),
                        (places, "a place count")):
        if not isinstance(value, int) or isinstance(value, bool):
            raise CalcError(f"{name} is a whole number, got {value!r}")
    if denominator == 0:
        raise CalcError("division by zero has no value")
    if places < 0 or places > 12:
        raise CalcError(f"places is between 0 and 12, got {places}")
    scale = 10 ** places
    numerator = numerator * scale
    sign = -1 if (numerator < 0) != (denominator < 0) else 1
    numerator, denominator = abs(numerator), abs(denominator)
    quotient, remainder = divmod(numerator, denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return sign * quotient


# --------------------------------------------------------------------------- #
# The legacy path
# --------------------------------------------------------------------------- #
def legacy_calculate(text: str):
    """`eval(expression)`, with no builtins -- the transcribed calculator.

    Still Python, not arithmetic: `^` is XOR, `/` is float division, and anything
    that names a value raises `NameError`.
    """
    return eval(text, {"__builtins__": {}}, {})          # noqa: S307


# --------------------------------------------------------------------------- #
# Reading the bundle
# --------------------------------------------------------------------------- #
def parse_expressions(text: str) -> tuple[str, ...]:
    """Read one expression per line; `;` introduces a comment."""
    lines: list[str] = []
    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        body = line.split(";", 1)[0].strip()
        if not body:
            continue
        if "#" in body:
            raise CalcError(f"line {number}: a comment starts with ';', not '#'")
        lines.append(body)
    if not lines:
        raise CalcError("a bundle needs at least one expression")
    return tuple(lines)


def read_expressions(path=None) -> tuple[str, ...]:
    target = Path(EXPRESSIONS_FILE if path is None else path)
    if not target.is_file():
        raise CalcError(f"file not found: {target}")
    return parse_expressions(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Result:
    """One expression, what `eval` said, what the calculator said, and what shows."""

    expression: str
    legacy: str
    shown: str
    places: int

    def __post_init__(self) -> None:
        if not isinstance(self.expression, str) or not self.expression.strip():
            raise CalcError("a result names the expression it came from")
        if not isinstance(self.legacy, str):
            raise CalcError("a legacy answer is text, even when it is a crash")
        if not isinstance(self.shown, str) or not self.shown.strip():
            raise CalcError("a result carries the digits it shows")
        if not isinstance(self.places, int) or isinstance(self.places, bool):
            raise CalcError(f"a place count is a whole number, got {self.places!r}")
        if self.places < 0:
            raise CalcError(f"a place count is at least 0, got {self.places}")

    def differs(self) -> bool:
        """Does the legacy answer disagree with the display, even after rounding?

        `0.1 + 0.2` is `0.30000000000000004`, which rounds to `0.3` -- that one
        differs only in spelling. `2 ^ 3` is `1`, which does not round to `8`: a
        disagreement that survives rounding is an answer that is wrong.
        """
        if self.legacy == "crash" or self.shown.startswith("refused:"):
            return True
        try:
            left = Decimal(self.legacy)
            right = Decimal(self.shown)
        except (InvalidOperation, ValueError):
            return True
        if left == right:
            return False
        try:
            return render(left, self.places) != self.shown
        except CalcError:
            return True

    def line(self) -> str:
        return f"{self.expression:<18} eval={self.legacy:<22} shows={self.shown}"


def compare(expressions, places: int = PLACES) -> tuple[Result, ...]:
    """Evaluate every expression both ways, recording a refusal as a sentence."""
    results: list[Result] = []
    for expression in expressions:
        try:
            answer = legacy_calculate(expression)
            legacy = repr(answer) if isinstance(answer, float) else str(answer)
        except Exception as error:                          # noqa: BLE001
            legacy = "crash" if isinstance(error, ZeroDivisionError) else \
                f"{type(error).__name__}"
        try:
            shown = render(evaluate(expression), places)
        except CalcError as error:
            results.append(Result(expression, legacy, f"refused: {error}", places))
            continue
        results.append(Result(expression, legacy, shown, places))
    return tuple(results)


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(results, refusals) -> list[tuple[str, bool]]:
    """Eleven checks, re-derived from the results and refusals the demo produced."""
    def find(expression: str) -> Result:
        for result in results:
            if result.expression.replace(" ", "") == expression.replace(" ", ""):
                return result
        raise CalcError(f"no result for {expression!r}")

    def the_legacy_adder_shows_seventeen_digits() -> bool:
        result = find("0.1+0.2")
        return result.legacy.startswith("0.30000000000000004") and \
            result.shown == "0.3"

    def the_legacy_caret_is_exclusive_or() -> bool:
        result = find("2^3")
        return result.legacy == "1" and result.shown == "8"

    def a_division_by_zero_is_a_sentence() -> bool:
        result = find("10/0")
        return result.legacy == "crash" and result.shown.startswith("refused:")

    def rounding_is_half_up_not_half_even() -> bool:
        result = find("2.675")
        return result.legacy == "2.675" and \
            render(Decimal("2.675"), 2) == "2.68"

    def multiplication_binds_tighter_than_addition() -> bool:
        return find("2+3*4").shown == "14"

    def power_is_right_associative() -> bool:
        return find("2^3^2").shown == "512"

    def unary_minus_binds_looser_than_power() -> bool:
        return find("-2^2").shown == "-4"

    def brackets_change_the_answer() -> bool:
        return find("(2+3)*4").shown == "20"

    def a_result_wider_than_the_display_is_refused() -> bool:
        for expression, note in refusals:
            if expression.replace(" ", "") == "99999999999999*99":
                return note.startswith("refused:") and "digits" in note
        return False

    def every_expression_produced_one_row() -> bool:
        if len(results) != len(set(result.expression for result in results)):
            return False
        return all(result.expression.strip() for result in results)

    def the_integer_route_agrees_with_the_display() -> bool:
        """`divide_half_up(2675, 1000, 2)` is 268, and the display says 2.68."""
        digits = divide_half_up(2675, 1000, 2)
        return find("2.675").shown == f"{digits // 100}.{digits % 100:02d}"

    checks = [
        ("the legacy adder shows seventeen digits",
         the_legacy_adder_shows_seventeen_digits),
        ("the legacy caret is exclusive or",
         the_legacy_caret_is_exclusive_or),
        ("a division by zero is a sentence",
         a_division_by_zero_is_a_sentence),
        ("rounding is half-up, not half-even",
         rounding_is_half_up_not_half_even),
        ("multiplication binds tighter than addition",
         multiplication_binds_tighter_than_addition),
        ("power is right-associative", power_is_right_associative),
        ("unary minus binds looser than power",
         unary_minus_binds_looser_than_power),
        ("brackets change the answer", brackets_change_the_answer),
        ("a result wider than the display is refused",
         a_result_wider_than_the_display_is_refused),
        ("every expression produced one row",
         every_expression_produced_one_row),
        ("two routes to the same hundredths agree",
         the_integer_route_agrees_with_the_display),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    expressions = read_expressions()

    print("=" * 78)
    print(" CALCULATOR LAB - a display is not a number")
    print("=" * 78)

    print("\n  the legacy calculator, transcribed:")
    for line in LEGACY_CALCULATE.split("\n"):
        print(f"    {line}")

    shown = compare(expressions)
    print(f"\n  {len(shown)} expressions, evaluated both ways:")
    print(f"    {'expression':<18} {'eval says':<24} this calculator")
    for result in shown:
        print(f"    {result.expression:<18} {result.legacy:<24} {result.shown}")

    differing = [result for result in shown if result.differs()]
    print(f"\n    {len(differing)} of {len(shown)} disagree as numbers:")
    for result in differing:
        print(f"      {result.expression:<18} eval={result.legacy:<22} "
              f"shows={result.shown}")

    refusals = [(result.expression, result.shown) for result in shown
                if result.shown.startswith("refused:")]
    print(f"\n  {len(refusals)} expression(s) the calculator refuses rather than "
          f"answers:")
    for expression, note in refusals:
        print(f"    {expression:<40} {note}")

    print("\n  the precedence it reads, spelled out:")
    for expression, meaning in (
            ("2 + 3 * 4", "(2 + (3 * 4))"),
            ("2 ^ 3 ^ 2", "(2 ^ (3 ^ 2))"),
            ("-2 ^ 2", "(-(2 ^ 2))"),
            ("(2 + 3) * 4", "((2 + 3) * 4)")):
        print(f"    {expression:<14} is {meaning:<20} = "
              f"{render(evaluate(expression), 0)}")

    print("\n  what one character means, twice:")
    print(f"    eval('2 ^ 3')  -> {legacy_calculate('2 ^ 3')}  (xor)")
    print(f"    evaluate('2 ^ 3') -> {render(evaluate('2 ^ 3'), 0)}  (power)")

    print("\n  the same number, three ways to round it:")
    print(f"    Decimal('2.675') rounded half-up to 2 places  -> "
          f"{render(Decimal('2.675'), 2)}")
    print(f"    round(2.675, 2)                              -> "
          f"{round(2.675, 2)}")
    print(f"    divide_half_up(2675, 1000, 2)                -> "
          f"{divide_half_up(2675, 1000, 2)} hundredths, which is 2.68")

    checks = audit(shown, refusals)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{len(expressions)} expressions, {len(differing)} numeric "
          f"disagreement(s), {len(refusals)} refusal(s), 2^3 is "
          f"{legacy_calculate('2 ^ 3')} to eval and "
          f"{render(evaluate('2 ^ 3'), 0)} to the calculator, 2.675 rounds to "
          f"{render(Decimal('2.675'), 2)} half-up and {round(2.675, 2)} as a "
          f"double, and {sum(1 for _, okay in checks if okay)}/{len(checks)} "
          f"checks hold")

    print("\nDemo completed successfully.")
    return 0
