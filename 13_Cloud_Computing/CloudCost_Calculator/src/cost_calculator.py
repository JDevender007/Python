"""A monthly bill is a whole number of cents; a unit price is not.

The legacy calculator did what a spreadsheet does:

    total = 0.0
    for line in bill:
        total += line.quantity * float(line.price_usd)
    return round(total * 100)

Three separate mistakes live in those three lines.

**1. A unit price is not a bill.** `$0.145` is 14.5 cents, and `$1.005` is
100.5 cents. A bill, however, is charged in whole cents, so the half has to be
rounded -- half-up, in public, once. `round()` does not do that: it rounds half
to even, and worse, `0.145 * 100` is `14.499999999999998`, so the float path
rounds *down* where half-up rounds *up*. A line of 3 at `$0.145` is 44 cents
here and 43 cents there; a line of 1 at `$2.675` is 268 here and 267 there.

**2. Adding floats adds their errors.** Each line is a double that is already
slightly wrong, and the sum is wrong by a different amount again. Seven lines
that should cost 4985 cents come to 4983, and no amount of re-rounding the
total repairs the lines it was built from.

**3. A price with more precision than a bill can express is refused.** A tenth
of a cent is the finest granularity this module stores -- `$0.0234` is not
2.34 tenths, it is a price the caller has to decide how to round. Silently
truncating it is how a bill disagrees with its invoice.

So prices are parsed to integer tenths of a cent, a line is
`divide_half_up(quantity * price_tenths, 10)`, and every total is a sum of
those integers. Tiered pricing is billed tier by tier, each tier rounded at
its own boundary, so the 101st unit is priced at the second tier rather than
the first. The legacy float path is kept beside the correct one, executable,
so every claim above is reproduced with a number.

The demonstration is offline: seven bundled bill lines and one tier table.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BILL_FILE = DATA_DIR / "bill.txt"

#: The legacy total, transcribed -- and executable.
LEGACY_TOTAL = ('total = 0.0\n'
                'for line in bill:\n'
                '    total += line.quantity * float(line.price_usd)\n'
                'return round(total * 100)')

#: The legacy tier shortcut: the marginal rate applied to every unit.
LEGACY_TIER = "return round(units * tiers[-1][1] / 10)"

#: A unit price is stored in tenths of a cent, because a cent is not fine enough.
PRICE_SCALE = 10

#: The tier table: a width in units and a price in tenths of a cent per unit.
TIERS = ((100, 25), (400, 15), (None, 9))

#: The budget the bundled bill is measured against, in cents ($50.00).
BUDGET_CENTS = 5000

#: The field separator a bill line uses.
FIELD = "|"


class DomainError(Exception):
    """A price, a quantity, a line or a tier table the program refuses."""


# --------------------------------------------------------------------------- #
# Integer arithmetic
# --------------------------------------------------------------------------- #
def divide_half_up(numerator: int, denominator: int) -> int:
    """`numerator / denominator` rounded half-up, from integers only."""
    for value, name in ((numerator, "a numerator"), (denominator, "a denominator")):
        if not isinstance(value, int) or isinstance(value, bool):
            raise DomainError(f"{name} is a whole number, got {value!r}")
    if denominator <= 0:
        raise DomainError(f"a denominator is positive, got {denominator}")
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return sign * quotient


def _whole(value, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise DomainError(f"{name} is a whole number, got {value!r}")
    return value


def _text(value, name: str) -> str:
    if not isinstance(value, str):
        raise DomainError(f"{name} is text, got {type(value).__name__}")
    if not value.strip():
        raise DomainError(f"{name} is text, and not blank")
    return value


# --------------------------------------------------------------------------- #
# Prices and amounts
# --------------------------------------------------------------------------- #
def parse_price(text: str) -> int:
    """`"$0.145" -> 145` tenths of a cent; three decimals at most."""
    _text(text, "a price")
    body = text.strip()
    if body.startswith("$"):
        body = body[1:].strip()
    if not body:
        raise DomainError(f"a price is a dollar amount, got {text!r}")
    if body.startswith("-"):
        raise DomainError(f"a price is not negative, got {text!r}")
    whole, dot, fraction = body.partition(".")
    if not whole.isdigit():
        raise DomainError(f"a price is a dollar amount, got {text!r}")
    if dot and (not fraction or not fraction.isdigit()):
        raise DomainError(f"a price is a dollar amount, got {text!r}")
    if len(fraction) > 3:
        raise DomainError(f"a price has at most three decimals -- tenths of a "
                          f"cent -- got {text!r}")
    return int(whole) * 1000 + int((fraction + "000")[:3])


def format_price(tenths: int) -> str:
    """`145 -> "$0.145"`, `1005 -> "$1.005"`, `100 -> "$0.10"`."""
    _whole(tenths, "a price")
    sign = "-" if tenths < 0 else ""
    whole, part = divmod(abs(tenths), 1000)
    digits = f"{part:03d}".rstrip("0")
    if len(digits) < 2:
        digits = (digits + "00")[:2]
    return f"{sign}${whole}.{digits}"


def format_cents(cents: int) -> str:
    """`4985 -> "$49.85"`, `5 -> "$0.05"` -- integer cents, never a float."""
    _whole(cents, "an amount of cents")
    sign = "-" if cents < 0 else ""
    whole, part = divmod(abs(cents), 100)
    return f"{sign}${whole}.{part:02d}"


# --------------------------------------------------------------------------- #
# A line and a bill
# --------------------------------------------------------------------------- #
def line_cents(quantity: int, price_tenths: int) -> int:
    """`3 x 145 tenths -> 44 cents`: one half-up rounding per line."""
    _whole(quantity, "a quantity")
    _whole(price_tenths, "a price")
    if quantity < 0:
        raise DomainError(f"a quantity is not negative, got {quantity}")
    if price_tenths < 0:
        raise DomainError(f"a price is not negative, got {price_tenths}")
    return divide_half_up(quantity * price_tenths, PRICE_SCALE)


def legacy_line_cents(quantity: int, price_usd: float) -> int:
    """`round(quantity * float(price) * 100)` -- half to even, on a wrong double."""
    if not isinstance(price_usd, (int, float)) or isinstance(price_usd, bool):
        raise DomainError(f"a legacy price is a float, got {price_usd!r}")
    return int(round(quantity * float(price_usd) * 100))


@dataclass(frozen=True)
class BillLine:
    """One usage row: a service, a SKU, a whole quantity and a tenth-of-a-cent price."""

    service: str
    sku: str
    quantity: int
    price_tenths: int

    def __post_init__(self) -> None:
        _text(self.service, "a service")
        _text(self.sku, "a sku")
        _whole(self.quantity, "a quantity")
        if self.quantity < 0:
            raise DomainError(f"a quantity is not negative, got {self.quantity}")
        _whole(self.price_tenths, "a price")
        if self.price_tenths < 0:
            raise DomainError(f"a price is not negative, got {self.price_tenths}")

    def total_cents(self) -> int:
        return line_cents(self.quantity, self.price_tenths)

    def legacy_cents(self) -> int:
        return legacy_line_cents(self.quantity, self.price_tenths / 1000)

    def agrees(self) -> bool:
        return self.total_cents() == self.legacy_cents()

    def head(self) -> str:
        return (f"{self.service:<10} {self.sku:<13} {self.quantity:>5} "
                f"{format_price(self.price_tenths):>8}")

    def row(self) -> str:
        mark = "" if self.agrees() else "  <-"
        return (f"{self.head()} {self.total_cents():>7} "
                f"{self.legacy_cents():>7}{mark}")


def _lines(rows) -> tuple[BillLine, ...]:
    held = tuple(rows)
    for row in held:
        if not isinstance(row, BillLine):
            raise DomainError(f"a bill holds lines, got {row!r}")
    return held


def bill_total(lines) -> int:
    """Every line rounded to cents, then added: the only order that is exact."""
    return sum(row.total_cents() for row in _lines(lines))


def legacy_bill_total(lines) -> int:
    """Every line as a float, summed, then rounded: the legacy bill."""
    return sum(row.legacy_cents() for row in _lines(lines))


def disagreements(lines) -> tuple[BillLine, ...]:
    """The lines where the integer bill and the float bill differ."""
    return tuple(row for row in _lines(lines) if not row.agrees())


# --------------------------------------------------------------------------- #
# Tiered pricing
# --------------------------------------------------------------------------- #
def _tier_table(tiers) -> tuple:
    held = tuple(tiers)
    if not held:
        raise DomainError("a tier table needs at least one tier")
    for index, tier in enumerate(held):
        if not isinstance(tier, tuple) or len(tier) != 2:
            raise DomainError(f"a tier is (width, price), got {tier!r}")
        width, price = tier
        last = index == len(held) - 1
        if width is None and not last:
            raise DomainError("only the last tier may be open ended")
        if width is not None:
            _whole(width, "a tier width")
            if width <= 0:
                raise DomainError(f"a tier width is positive, got {width}")
        _whole(price, "a tier price")
        if price < 0:
            raise DomainError(f"a tier price is not negative, got {price}")
    return held


def tiered_cents(units: int, tiers=TIERS) -> int:
    """Each tier is billed for its own units and rounded at its own boundary."""
    _whole(units, "a number of units")
    if units < 0:
        raise DomainError(f"a number of units is not negative, got {units}")
    table = _tier_table(tiers)
    remaining = units
    total = 0
    for width, price in table:
        if remaining <= 0:
            break
        take = remaining if width is None else min(remaining, width)
        total += divide_half_up(take * price, PRICE_SCALE)
        remaining -= take
    if remaining:
        raise DomainError(f"a tier table leaves {remaining} unit(s) unpriced")
    return total


def legacy_tiered_cents(units: int, tiers=TIERS) -> int:
    """The marginal rate applied to every unit -- the shortcut that overcharges."""
    _whole(units, "a number of units")
    if units < 0:
        raise DomainError(f"a number of units is not negative, got {units}")
    table = _tier_table(tiers)
    return divide_half_up(units * table[-1][1], PRICE_SCALE)


def budget_status(total_cents: int, budget_cents: int = BUDGET_CENTS) -> str:
    """A budget comparison, made in cents and reported in dollars."""
    _whole(total_cents, "a total")
    _whole(budget_cents, "a budget")
    if budget_cents < 0:
        raise DomainError(f"a budget is not negative, got {budget_cents}")
    difference = budget_cents - total_cents
    if difference == 0:
        return "on budget"
    if difference > 0:
        return f"under by {format_cents(difference)}"
    return f"over by {format_cents(-difference)}"


# --------------------------------------------------------------------------- #
# Reading the bill
# --------------------------------------------------------------------------- #
def parse_bill(text: str) -> tuple[BillLine, ...]:
    """Read `service | sku | quantity | price` per line; `#` introduces a comment."""
    rows: list[BillLine] = []
    for number, raw in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        body = raw.split("#", 1)[0].strip()
        if not body:
            continue
        fields = [field.strip() for field in body.split(FIELD)]
        if len(fields) != 4:
            raise DomainError(f"line {number}: four fields are needed -- a "
                              f"service, a SKU, a quantity and a price -- got "
                              f"{len(fields)}")
        service, sku, quantity_text, price_text = fields
        try:
            quantity = int(quantity_text)
        except ValueError:
            raise DomainError(f"line {number}: {quantity_text!r} is not a whole "
                              f"quantity") from None
        try:
            price = parse_price(price_text)
        except DomainError as error:
            raise DomainError(f"line {number}: {error}") from None
        try:
            rows.append(BillLine(service, sku, quantity, price))
        except DomainError as error:
            raise DomainError(f"line {number}: {error}") from None
    if not rows:
        raise DomainError("a bill needs at least one line")
    return tuple(rows)


def read_bill(path=None) -> tuple[BillLine, ...]:
    target = Path(BILL_FILE if path is None else path)
    if not target.is_file():
        raise DomainError(f"file not found: {target}")
    return parse_bill(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(measured: dict, lines, make_line=BillLine) -> list[tuple[str, bool]]:
    """Thirteen checks, each one falsifiable from a measurement or the bill."""
    def at(name: str):
        if name not in measured:
            raise DomainError(f"no measurement named {name!r}")
        return measured[name]

    def a_price_keeps_a_tenth_of_a_cent() -> bool:
        return at("price_1_005") == 1005 and at("price_0_023") == 23 and \
            at("precise_refused") is True

    def a_line_rounds_half_up_not_by_a_float() -> bool:
        return at("line_1005") == 101 and at("legacy_line_1005") == 100

    def three_at_a_half_cent_round_up() -> bool:
        return at("line_145_x3") == 44 and at("legacy_line_145_x3") == 43

    def a_bill_is_not_the_sum_of_its_floats() -> bool:
        return at("total") == 5716 and at("legacy_total") == 5714 and \
            at("total") != at("legacy_total")

    def two_rows_disagree() -> bool:
        return at("differing") == ["requests", "archive"]

    def every_line_rebuilds_from_its_fields() -> bool:
        rebuilt = sum(make_line(row.service, row.sku, row.quantity,
                                row.price_tenths).total_cents() for row in lines)
        return rebuilt == at("total")

    def a_tier_boundary_is_inclusive_of_its_last_unit() -> bool:
        return at("tiers_100") == 250

    def one_unit_past_the_boundary_takes_the_next_rate() -> bool:
        return at("tiers_101") == 252

    def each_tier_rounds_at_its_own_boundary() -> bool:
        return at("tiers_550") == 895

    def the_marginal_rate_on_every_unit_is_the_legacy_error() -> bool:
        return at("legacy_tiers_550") == 495

    def a_bill_is_printed_from_integer_cents() -> bool:
        return at("formatted_total") == "$57.16" and \
            at("formatted_nickel") == "$0.05"

    def a_budget_is_compared_in_cents() -> bool:
        return at("budget") == "over by $7.16"

    def a_price_is_never_a_float() -> bool:
        return at("float_input_refused") is True

    checks = [
        ("a price keeps a tenth of a cent", a_price_keeps_a_tenth_of_a_cent),
        ("a line rounds half up, not by a float",
         a_line_rounds_half_up_not_by_a_float),
        ("three at a half cent round up", three_at_a_half_cent_round_up),
        ("a bill is not the sum of its floats", a_bill_is_not_the_sum_of_its_floats),
        ("two rows disagree", two_rows_disagree),
        ("every line rebuilds from its fields", every_line_rebuilds_from_its_fields),
        ("a tier boundary keeps its last unit",
         a_tier_boundary_is_inclusive_of_its_last_unit),
        ("one unit past the boundary takes the next rate",
         one_unit_past_the_boundary_takes_the_next_rate),
        ("each tier rounds at its own boundary",
         each_tier_rounds_at_its_own_boundary),
        ("the marginal rate on every unit is the legacy error",
         the_marginal_rate_on_every_unit_is_the_legacy_error),
        ("a bill is printed from integer cents",
         a_bill_is_printed_from_integer_cents),
        ("a budget is compared in cents", a_budget_is_compared_in_cents),
        ("a price is never a float", a_price_is_never_a_float),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def measure(lines) -> dict:
    """Every number the audit is allowed to read, measured once."""
    held = _lines(lines)
    total = bill_total(held)
    measured = {
        "price_1_005": parse_price("1.005"),
        "price_0_023": parse_price("0.023"),
        "precise_refused": not _guard(lambda: parse_price("0.0234")),
        "line_1005": line_cents(1, 1005),
        "legacy_line_1005": legacy_line_cents(1, 1.005),
        "line_145_x3": line_cents(3, 145),
        "legacy_line_145_x3": legacy_line_cents(3, 0.145),
        "total": total,
        "legacy_total": legacy_bill_total(held),
        "differing": [row.service for row in disagreements(held)],
        "tiers_100": tiered_cents(100),
        "tiers_101": tiered_cents(101),
        "tiers_550": tiered_cents(550),
        "legacy_tiers_550": legacy_tiered_cents(550),
        "formatted_total": format_cents(total),
        "formatted_nickel": format_cents(5),
        "budget": budget_status(total, BUDGET_CENTS),
        "sum_of_parts": total,
        "float_input_refused": not _guard(lambda: parse_price(1.5)),
    }
    return measured


def run_demo() -> int:
    lines = read_bill()
    measured = measure(lines)

    print("=" * 78)
    print(" CLOUD COST LAB - a bill is cents, a unit price is not")
    print("=" * 78)

    print("\n  the legacy total, transcribed:")
    for line in LEGACY_TOTAL.split("\n"):
        print(f"    {line}")

    print(f"\n  {len(lines)} lines from data/bill.txt:")
    print(f"    {'service':<10} {'sku':<13} {'qty':>5} {'price':>8} "
          f"{'cents':>7} {'float':>7}")
    for row in lines:
        print(f"    {row.row()}")

    total = measured["total"]
    legacy = measured["legacy_total"]
    print(f"\n  the bill is {total} cents here, {legacy} cents from floats: "
          f"{legacy - total} cents apart")
    print("  a cent is rounded half-up per line, and the lines are integers:")
    for service in measured["differing"]:
        row = next(item for item in lines if item.service == service)
        print(f"    {service:<10} {row.quantity} x "
              f"{format_price(row.price_tenths)} = "
              f"{format_price(row.quantity * row.price_tenths)} -> "
              f"{row.total_cents()} cents half-up, "
              f"{row.legacy_cents()} from the float")

    print("\n  a price carries a tenth of a cent; the bill does not:")
    print(f"    $1.005 -> {measured['line_1005']} cents for one unit, "
          f"{measured['legacy_line_1005']} from the float")
    print(f"    3 x $0.145 -> {measured['line_145_x3']} cents, "
          f"{measured['legacy_line_145_x3']} from the float")
    print(f"    $0.0234 is refused: three decimals is the limit "
          f"({measured['precise_refused']})")

    print("\n  tiers: first 100 units at 2.5 cents, next 400 at 1.5, the rest 0.9")
    print(f"    100 units -> {measured['tiers_100']} cents")
    print(f"    101 units -> {measured['tiers_101']} cents "
          f"(the 101st unit takes the second rate)")
    print(f"    550 units -> {measured['tiers_550']} cents, "
          f"tier by tier")
    print(f"    the marginal rate on all 550 -> "
          f"{measured['legacy_tiers_550']} cents (the legacy shortcut)")
    print(f"    the legacy line, transcribed: {LEGACY_TIER}")

    print(f"\n  {format_cents(total)} against a "
          f"{format_cents(BUDGET_CENTS)} budget: {measured['budget']}")

    checks = audit(measured, lines)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    passed = sum(1 for _, okay in checks if okay)
    print(f"  {passed}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{len(lines)} lines cost {total} cents as integers against {legacy} "
          f"from floats, {len(measured['differing'])} rows disagree because "
          f"3 x $0.145 is {measured['line_145_x3']} cents half-up not "
          f"{measured['legacy_line_145_x3']} and $0.265 is 27 cents not 26, "
          f"100 units cost {measured['tiers_100']} cents while 101 cost "
          f"{measured['tiers_101']}, 550 units cost "
          f"{measured['tiers_550']} cents tier by tier against "
          f"{measured['legacy_tiers_550']} at the marginal rate, and "
          f"{passed}/{len(checks)} checks hold")

    print("Demo completed successfully.")
    return 0
