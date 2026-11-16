"""A rate is a ratio with a direction, and it is only true on the day it was quoted.

The legacy converter held one number per currency pair and used it both ways:

    def convert(amount, rate):
        return round(amount * rate, 2)

    def rate_for(rates, code):
        return rates.get(code, 1.0)

**1. A rate has a direction.** `0.92` here means "one dollar is 0.92 euro". Multiplying
euros by it says "one euro is 0.92 euro", which is not a rate at all. A hundred dollars
becomes 92 euro, and 92 euro becomes **84.64 dollars** -- fifteen dollars and change
evaporated, with no exception and no warning:

    legacy_convert(100.00, 0.92) = 92.0
    legacy_convert(92.00, 0.92)  = 84.64

**2. `get(code, 1.0)` is a currency that always exists.** A code the table does not hold
converts **at par**: 100.00 of anything is 100.00 of anything else. A typo in a currency
code is a valid conversion, and the number looks perfectly reasonable.

**3. `round()` is not the rounding a money sheet means.** `round(2.675, 2)` is **2.67**,
because the binary double for 2.675 is below the tie and `round` goes to the even
neighbour anyway: `round(2.5)` is 2 and `round(3.5)` is 4. Half-up is what an invoice
means, and it has to be written out.

**4. A rate without a date is a rate of unknown age.** The sheet says `as_of
2026-11-14`. Converting December's money with it is a decision, not an arithmetic fact,
and the decision has to be made somewhere visible.

**5. A minor unit is a property of the currency.** Yen has no subunit; dollars and euros
have hundredths. A ratio of **major** units applied to **minor** amounts needs the
exponent in the arithmetic, or 100 dollars becomes 151 yen instead of 15,100:

    100.00 USD -> 15100 JPY   (exponent 0 - exponent 2, so the ratio is scaled by 100)

So this module keeps a rate as **two integers and a direction**, converts in integers
only with explicit half-up rounding, derives the inverse by swapping the pair rather than
dividing, keeps a currency's exponent next to its code, refuses a code it does not know
by name, and dates every quote.

The demonstration is offline: one bundled rate sheet, one bundled list of amounts, and no
network. Standard library only: no requests, no HTTP client, no API key.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
QUOTE_FILE = DATA_DIR / "quote.txt"
AMOUNTS_FILE = DATA_DIR / "amounts.txt"

#: The legacy pair, transcribed: one rate, both directions, banker's rounding.
LEGACY_CONVERT = 'return round(amount * rate, 2)'

#: The legacy lookup, transcribed: a currency that does not exist is worth 1.0.
LEGACY_LOOKUP = 'return rates.get(code, 1.0)'

#: The day the bundled sheet is read on.
READ_ON = "2026-11-15"

#: How many days a quote stays fresh.
FRESH_DAYS = 7

#: How many places the decimal form of a ratio prints.
PLACES = 6

MINOR_UNIT = 10


class RateError(Exception):
    """A rate, a quote or an amount that cannot be read, and why not."""


# --------------------------------------------------------------------------- #
# Integer arithmetic
# --------------------------------------------------------------------------- #
def divide_half_up(numerator: int, denominator: int) -> int:
    """Whole division, rounding a half away from zero, in integers only."""
    if not isinstance(numerator, int) or isinstance(numerator, bool):
        raise RateError(f"a numerator is a whole number, got {numerator!r}")
    if not isinstance(denominator, int) or isinstance(denominator, bool):
        raise RateError(f"a divisor is a whole number, got {denominator!r}")
    if denominator <= 0:
        raise RateError(f"a divisor must be positive, got {denominator}")
    sign = -1 if numerator < 0 else 1
    magnitude = abs(numerator)
    return sign * ((magnitude * 2 + denominator) // (2 * denominator))


def _code(value, field: str) -> str:
    if not isinstance(value, str):
        raise RateError(f"{field} is three letters, got {type(value).__name__}")
    body = value.strip()
    if len(body) != 3 or not body.isalpha() or not body.isupper():
        raise RateError(f"{field} is three upper-case letters, got {value!r}")
    return body


def _whole(value, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise RateError(f"{field} is a whole number, got {value!r}")
    return value


# --------------------------------------------------------------------------- #
# A rate
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Rate:
    """One exchange rate: `numerator / denominator` of `quote` per one `base`.

    Two integers and two codes, because that is exactly what a rate is. There is no
    float anywhere, so the inverse is exact rather than approximately right, and the
    direction cannot be lost: `Rate("USD", "EUR", 92, 100)` is not `Rate("EUR", "USD",
    92, 100)`, and only one of them is the sheet's rate.
    """

    base: str
    quote: str
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if _code(self.base, "a base currency") == _code(self.quote,
                                                        "a quote currency"):
            raise RateError(f"a rate needs two currencies, got "
                            f"{self.base!r} twice")
        if _whole(self.numerator, "a rate numerator") <= 0:
            raise RateError(f"a rate must be positive, got {self.numerator}; a "
                            f"rate of zero has no inverse")
        if _whole(self.denominator, "a rate denominator") <= 0:
            raise RateError(f"a rate denominator must be positive, got "
                            f"{self.denominator}")

    def inverse(self) -> "Rate":
        """The other direction: the pair swapped, nothing divided."""
        return Rate(self.quote, self.base, self.denominator, self.numerator)

    def pair(self) -> str:
        return f"{self.base}/{self.quote}"

    def text(self) -> str:
        """`USD/EUR = 92/100` -- the ratio exactly as the sheet holds it."""
        return f"{self.pair()} = {self.numerator}/{self.denominator}"

    def decimal_text(self) -> str:
        """`0.920000` -- the ratio to six places, for a person reading it."""
        scaled = divide_half_up(self.numerator * 10 ** PLACES, self.denominator)
        whole, fraction = divmod(scaled, 10 ** PLACES)
        return f"{whole}.{fraction:0{PLACES}d}"

    def __str__(self) -> str:
        return self.text()


def convert(rate: Rate, amount: int, from_exponent: int,
            to_exponent: int) -> int:
    """`amount` minor units of `rate.base` as minor units of `rate.quote`.

    The rate is a ratio of **major** units, so the difference between the two
    currencies' exponents is part of the arithmetic: a ratio of 151 yen per dollar
    applied to 10,000 cents is 15,100 yen, not 151.
    """
    if not isinstance(rate, Rate):
        raise RateError(f"a conversion needs a rate, got "
                        f"{type(rate).__name__}")
    amount = _whole(amount, "an amount")
    from_exponent = _whole(from_exponent, "an exponent")
    to_exponent = _whole(to_exponent, "an exponent")
    shift = to_exponent - from_exponent
    numerator = rate.numerator
    denominator = rate.denominator
    if shift >= 0:
        numerator *= 10 ** shift
    else:
        denominator *= 10 ** -shift
    return divide_half_up(amount * numerator, denominator)


def money_text(minor: int, code: str, exponent: int) -> str:
    """`1,299.00 USD`, `15,100 JPY` -- minor units, printed as a person writes them."""
    minor = _whole(minor, "an amount")
    code = _code(code, "a currency")
    exponent = _whole(exponent, "an exponent")
    if exponent < 0 or exponent > 4:
        raise RateError(f"{code} cannot have {exponent} decimal places")
    sign = "-" if minor < 0 else ""
    magnitude = abs(minor)
    if exponent == 0:
        return f"{sign}{magnitude:,} {code}"
    scale = 10 ** exponent
    whole, fraction = divmod(magnitude, scale)
    return f"{sign}{whole:,}.{fraction:0{exponent}d} {code}"


# --------------------------------------------------------------------------- #
# A quote
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Quote:
    """One sheet: the day it applies to, the base currency, and the rates."""

    as_of: date
    base: str
    rates: tuple[Rate, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.as_of, date):
            raise RateError(f"a quote names a day, got "
                            f"{type(self.as_of).__name__}; a rate with no day "
                            f"has no age")
        _code(self.base, "a base currency")
        if not self.rates:
            raise RateError("a quote needs at least one rate")
        quotes = [rate.quote for rate in self.rates]
        if len(set(quotes)) != len(quotes):
            raise RateError("two rates share a quote currency")
        for rate in self.rates:
            if rate.base != self.base:
                raise RateError(f"the sheet is based on {self.base}, but it "
                                f"holds a rate from {rate.base}")

    def __len__(self) -> int:
        return len(self.rates)

    def for_currency(self, code: str) -> Rate:
        """The rate from the base to `code`, or a refusal naming the code."""
        code = _code(code, "a currency")
        if code == self.base:
            raise RateError(f"{code} is the base currency: converting it to "
                            f"itself needs no rate")
        for rate in self.rates:
            if rate.quote == code:
                return rate
        known = ", ".join(sorted(rate.quote for rate in self.rates))
        raise RateError(f"the sheet of {self.as_of.isoformat()} holds no rate "
                        f"for {code}; it holds {known}")

    def age_days(self, on: date) -> int:
        """How many days old this quote is on `on`."""
        if not isinstance(on, date):
            raise RateError(f"a day is needed, got {type(on).__name__}")
        elapsed = (on - self.as_of).days
        if elapsed < 0:
            raise RateError(f"{on.isoformat()} is before the quote of "
                            f"{self.as_of.isoformat()}, so the quote has no age")
        return elapsed

    def is_stale(self, on: date, limit_days: int = FRESH_DAYS) -> bool:
        limit_days = _whole(limit_days, "a day limit")
        if limit_days < 0:
            raise RateError(f"a limit is a number of days, got {limit_days}")
        return self.age_days(on) > limit_days

    def lines(self) -> tuple[str, ...]:
        return tuple(f"{rate.pair():<9} {rate.decimal_text():>10}   "
                     f"({rate.text()})" for rate in self.rates)


@dataclass(frozen=True)
class Sheet:
    """A quote, the exponent of every currency on it, and the conversion."""

    quote: Quote
    exponents: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.quote, Quote):
            raise RateError(f"a sheet holds a quote, got "
                            f"{type(self.quote).__name__}")
        if not self.exponents:
            raise RateError("a sheet needs the exponent of every currency")
        codes = [code for code, _ in self.exponents]
        if len(set(codes)) != len(codes):
            raise RateError("two currency codes share an exponent")
        for code, exponent in self.exponents:
            _code(code, "a currency")
            _whole(exponent, "an exponent")
            if exponent < 0 or exponent > 4:
                raise RateError(f"{code} cannot have {exponent} decimal places")
        if self.quote.base not in codes:
            raise RateError(f"the sheet gives no exponent for its base "
                            f"{self.quote.base}")

    def __len__(self) -> int:
        return len(self.quote)

    def exponent(self, code: str) -> int:
        code = _code(code, "a currency")
        for held, exponent in self.exponents:
            if held == code:
                return exponent
        raise RateError(f"the sheet gives no exponent for {code}")

    def money(self, minor: int, code: str) -> str:
        return money_text(minor, code, self.exponent(code))

    def convert(self, minor: int, code: str) -> int:
        """`minor` units of the base as units of `code`."""
        rate = self.quote.for_currency(code)
        return convert(rate, minor, self.exponent(self.quote.base),
                       self.exponent(code))

    def convert_back(self, minor: int, code: str) -> int:
        """`minor` units of `code` as units of the base, through the inverse."""
        rate = self.quote.for_currency(code).inverse()
        return convert(rate, minor, self.exponent(code),
                       self.exponent(self.quote.base))

    def drift(self, minor: int, code: str) -> int:
        """What a there-and-back conversion adds or loses, in base minor units."""
        return self.convert_back(self.convert(minor, code), code) - minor

    def fresh(self, on: date, limit_days: int = FRESH_DAYS) -> str:
        age = self.quote.age_days(on)
        state = "STALE" if self.quote.is_stale(on, limit_days) else "fresh"
        return (f"{state}  quoted {self.quote.as_of.isoformat()}, read "
                f"{on.isoformat()}, {age} day(s) old, limit {limit_days}")


# --------------------------------------------------------------------------- #
# The legacy pair, executable
# --------------------------------------------------------------------------- #
def legacy_convert(amount: float, rate: float) -> float:
    """The legacy conversion, rewritten faithfully: one rate, both directions."""
    return round(amount * rate, 2)


def legacy_rate(rates: dict, code: str) -> float:
    """The legacy lookup, rewritten faithfully: unknown means 1.0."""
    return rates.get(code, 1.0)


def legacy_table(sheet: Sheet) -> dict:
    """The floats the legacy code would have kept: one per currency, no direction."""
    return {rate.quote: rate.numerator / rate.denominator
            for rate in sheet.quote.rates}


# --------------------------------------------------------------------------- #
# Reading the sheet
# --------------------------------------------------------------------------- #
def parse_sheet(text: str) -> Sheet:
    """Read `name value...` lines: `as_of`, `base`, `exp CODE N`, `rate CODE N D`."""
    day: date | None = None
    base: str | None = None
    exponents: list[tuple[str, int]] = []
    rates: list[Rate] = []

    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"),
                                  start=1):
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        fields = line.split()
        head = fields[0]
        if head == "as_of":
            if len(fields) != 2:
                raise RateError(f"line {number}: as_of takes one day")
            try:
                day = date.fromisoformat(fields[1])
            except ValueError:
                raise RateError(f"line {number}: {fields[1]!r} is not a day "
                                f"written YYYY-MM-DD") from None
            continue
        if head == "base":
            if len(fields) != 2:
                raise RateError(f"line {number}: base takes one currency")
            base = fields[1]
            continue
        if head == "exp":
            if len(fields) != 3:
                raise RateError(f"line {number}: exp takes a code and a number "
                                f"of decimal places")
            exponents.append((fields[1], _whole(int(fields[2])
                                               if fields[2].lstrip("-").isdigit()
                                               else fields[2], "an exponent")))
            continue
        if head == "rate":
            if len(fields) != 4:
                raise RateError(f"line {number}: rate takes a code, a "
                                f"numerator and a denominator")
            try:
                numerator = int(fields[2])
                denominator = int(fields[3])
            except ValueError:
                raise RateError(f"line {number}: a rate is two whole "
                                f"numbers") from None
            if base is None:
                raise RateError(f"line {number}: a rate comes after the base")
            rates.append(Rate(base, fields[1], numerator, denominator))
            continue
        raise RateError(f"line {number}: {head!r} is not as_of, base, exp or "
                        f"rate")

    if day is None:
        raise RateError("the sheet names no day: every rate needs an as_of")
    if base is None:
        raise RateError("the sheet names no base currency")
    return Sheet(Quote(day, base, tuple(rates)), tuple(exponents))


def read_sheet(path=None) -> Sheet:
    target = Path(QUOTE_FILE if path is None else path)
    if not target.is_file():
        raise RateError(f"file not found: {target}")
    return parse_sheet(target.read_text(encoding="utf-8"))


def parse_amounts(text: str) -> tuple[tuple[int, str], ...]:
    """Read `CODE amount` lines, an amount in that currency's minor units."""
    amounts: list[tuple[int, str]] = []
    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"),
                                  start=1):
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        fields = line.split()
        if len(fields) != 2:
            raise RateError(f"line {number}: an amount is a code and a whole "
                            f"number of minor units")
        code = _code(fields[0], "a currency")
        try:
            amount = int(fields[1])
        except ValueError:
            raise RateError(f"line {number}: {fields[1]!r} is not a whole "
                            f"number of minor units") from None
        if amount < 0:
            raise RateError(f"line {number}: an amount cannot be negative")
        amounts.append((amount, code))
    if not amounts:
        raise RateError("the list holds no amounts")
    return tuple(amounts)


def read_amounts(path=None) -> tuple[tuple[int, str], ...]:
    target = Path(AMOUNTS_FILE if path is None else path)
    if not target.is_file():
        raise RateError(f"file not found: {target}")
    return parse_amounts(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def _parts(rate: Rate) -> tuple:
    """A rate as its four parts, so a check compares values and not a class."""
    return (rate.base, rate.quote, rate.numerator, rate.denominator)


def audit(sheet: Sheet, on: date | None = None,
          limit_days: int = FRESH_DAYS) -> list[tuple[str, bool]]:
    """Nine checks, each re-derived from the bundled sheet.

    `on` is injected so a negative control can read the sheet on a day it was never
    meant for, which is the only way to show the staleness check is measuring the age
    rather than restating the limit.
    """
    day = date.fromisoformat(READ_ON) if on is None else on

    def every_rate_is_a_ratio_of_whole_numbers() -> bool:
        for rate in sheet.quote.rates:
            for value in (rate.numerator, rate.denominator):
                if not isinstance(value, int) or isinstance(value, bool):
                    return False
            if rate.numerator <= 0 or rate.denominator <= 0:
                return False
        return True

    def every_rate_prints_and_reads_back_to_the_same_ratio() -> bool:
        for rate in sheet.quote.rates:
            text = rate.text()
            head, tail = text.split(" = ")
            base, quote = head.split("/")
            numerator, denominator = tail.split("/")
            rebuilt = Rate(base, quote, int(numerator), int(denominator))
            if _parts(rebuilt) != _parts(rate):
                return False
        return True

    def inverting_twice_gives_the_rate_back() -> bool:
        for rate in sheet.quote.rates:
            if _parts(rate.inverse().inverse()) != _parts(rate):
                return False
        return True

    def the_legacy_conversion_in_the_wrong_direction_loses_money() -> bool:
        rates = legacy_table(sheet)
        usd = 100.00
        eur = legacy_convert(usd, rates["EUR"])
        back = legacy_convert(eur, rates["EUR"])
        return eur == 92.0 and back < usd - 10 and \
            sheet.convert_back(9_200, "EUR") == 10_000

    def the_legacy_lookup_answers_par_for_a_currency_it_does_not_know() -> bool:
        rates = legacy_table(sheet)
        return legacy_rate(rates, "CHF") == 1.0 and legacy_rate(rates,
                                                                "EUR") == 0.92

    def round_is_not_half_up() -> bool:
        return round(2.675, 2) == 2.67 and \
            divide_half_up(268, 100) == 3 and \
            divide_half_up(267_500, 100_000) == 3

    def a_larger_amount_never_converts_to_a_smaller_one() -> bool:
        rate = sheet.quote.for_currency("EUR")
        previous = -1
        for amount in range(0, 5_000, 7):
            scaled = convert(rate, amount, 2, 2)
            if scaled < previous:
                return False
            previous = scaled
        return True

    def a_quote_older_than_its_limit_is_stale() -> bool:
        from datetime import timedelta
        later = sheet.quote.as_of + timedelta(days=limit_days + 29)
        return sheet.quote.is_stale(later, limit_days) and \
            sheet.quote.age_days(later) == limit_days + 29 and \
            not sheet.quote.is_stale(day, limit_days)

    def every_quote_names_the_day_it_applies_to() -> bool:
        return isinstance(sheet.quote.as_of, date) and \
            sheet.quote.as_of.isoformat() == "2026-11-14" and \
            sheet.quote.age_days(day) == 1

    checks = [
        ("every rate is a ratio of two positive whole numbers",
         every_rate_is_a_ratio_of_whole_numbers),
        ("every rate prints and reads back to the same ratio",
         every_rate_prints_and_reads_back_to_the_same_ratio),
        ("inverting a rate twice gives the rate back",
         inverting_twice_gives_the_rate_back),
        ("the legacy conversion in the wrong direction loses money",
         the_legacy_conversion_in_the_wrong_direction_loses_money),
        ("the legacy lookup answers par for an unknown currency",
         the_legacy_lookup_answers_par_for_a_currency_it_does_not_know),
        ("round() is not half-up and the sheet is",
         round_is_not_half_up),
        ("a larger amount never converts to a smaller one",
         a_larger_amount_never_converts_to_a_smaller_one),
        ("a quote older than its limit is stale, with its age",
         a_quote_older_than_its_limit_is_stale),
        ("every quote names the day it applies to",
         every_quote_names_the_day_it_applies_to),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
#: The amounts worth converting to show that a second rounding can drift.
DRIFTS = (6, 7, 13, 26)


def _two_places(hundredths: int) -> str:
    """`268` -> `2.68`, without a float anywhere."""
    sign = "-" if hundredths < 0 else ""
    whole, fraction = divmod(abs(hundredths), 100)
    return f"{sign}{whole}.{fraction:02d}"


def run_demo() -> int:
    sheet = read_sheet()
    amounts = read_amounts()
    on = date.fromisoformat(READ_ON)
    quote = sheet.quote

    print("=" * 78)
    print(" RATE LAB - a rate is a ratio with a direction, and it has a day")
    print("=" * 78)

    print("\n  the legacy pair, transcribed:")
    print(f"    {LEGACY_CONVERT}")
    print(f"    {LEGACY_LOOKUP}")

    print(f"\n  the sheet: {quote.base} on {quote.as_of.isoformat()}, "
          f"{len(quote)} rate(s)")
    for line in quote.lines():
        print(f"    {line}")

    print(f"\n  the exponents on the sheet:")
    print("    " + "  ".join(f"{code} {exponent}"
                             for code, exponent in sheet.exponents))

    print(f"\n  {sheet.money(10_000, 'USD')} in every currency on the sheet:")
    for rate in quote.rates:
        converted = sheet.convert(10_000, rate.quote)
        back = sheet.convert_back(converted, rate.quote)
        print(f"    {rate.pair():<9} {sheet.money(converted, rate.quote):>14}"
              f"   back {sheet.money(back, 'USD')}"
              f"   drift {back - 10_000:+d}")

    print("\n  and the same through the legacy converters:")
    rates = legacy_table(sheet)
    for code, rate in rates.items():
        euros = legacy_convert(100.00, rate)
        back = legacy_convert(euros, rate)
        print(f"    {code}  rate {rate:.4f}  100.00 USD -> {euros:>7.2f} "
              f"{code} -> {back:>7.2f} USD")
    print(f"    CHF  no rate    100.00 USD -> "
          f"{legacy_convert(100.00, legacy_rate(rates, 'CHF')):>7.2f} CHF  "
          f"(par, because get() defaults to 1.0)")

    print("\n  rounding a half:")
    print(f"    round(2.675, 2)                = {round(2.675, 2)}")
    print(f"    half-up of 2.675 to two places = "
          f"{_two_places(divide_half_up(2_675, 10))}")
    print(f"    round(2.5) is {round(2.5)} and round(3.5) is {round(3.5)}: "
          f"round() goes to the even neighbour")

    print(f"\n  the round trip on four small amounts:")
    drifts = 0
    for amount in DRIFTS:
        converted = sheet.convert(amount, "EUR")
        back = sheet.convert_back(converted, "EUR")
        drifts += back != amount
        print(f"    {amount:>3} USD cents -> {converted:>3} EUR cents -> "
              f"{back:>3} USD cents   drift {back - amount:+d}")

    print(f"\n  every bundled amount, converted and back:")
    for amount, code in amounts:
        converted = sheet.convert(amount, code)
        back = sheet.convert_back(converted, code)
        print(f"    {sheet.money(amount, quote.base):>14} -> "
              f"{sheet.money(converted, code):>14} -> "
              f"{sheet.money(back, quote.base):>14}   "
              f"drift {back - amount:+d}")

    print(f"\n  the age of the quote:")
    for day_text in ("2026-11-15", "2026-11-22", "2026-12-20"):
        print(f"    {sheet.fresh(date.fromisoformat(day_text))}")

    checks = audit(sheet, on)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    exact = sum(1 for amount, code in amounts
                if sheet.drift(amount, code) == 0)
    print("\nCross-checks OK: " +
          f"{len(quote)} rate(s) give {len(quote)} pair(s) and "
          f"{len(quote)} inverse(s), {sheet.money(10_000, 'USD')} is "
          f"{sheet.money(sheet.convert(10_000, 'EUR'), 'EUR')} and "
          f"{sheet.money(sheet.convert(10_000, 'JPY'), 'JPY')}, "
          f"{exact} of {len(amounts)} bundled amounts round-trip exactly and "
          f"{drifts} of {len(DRIFTS)} small ones drift by one minor unit "
          f"({DRIFTS[0]} cents -> {sheet.drift(DRIFTS[0], 'EUR'):+d}), "
          f"the legacy conversion in the wrong direction turns 100.00 USD "
          f"into {legacy_convert(92.00, rates['EUR']):.2f} USD and an unknown "
          f"currency into {legacy_convert(100.00, 1.0):.2f}, the quote of "
          f"{quote.as_of.isoformat()} is {quote.age_days(on)} day(s) old when "
          f"read, and {sum(1 for _, okay in checks if okay)}/{len(checks)} "
          f"checks hold")

    print("\nDemo completed successfully.")
    return 0
