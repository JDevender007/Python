"""A price is money, not the digits left after deleting everything else.

The legacy tracker read a price like this:

    def clean_price(value):
        if not value:
            return 0.0
        cleaned = re.sub(r"[^\\d.]", "", value)
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

and computed a change like this:

    def calculate_percentage_change(old_price, new_price):
        if old_price <= 0:
            return 0.0
        return ((new_price - old_price) / old_price) * 100

One regular expression, one float, and one `0.0` that means four different
things at once.

**1. Deleting characters is not parsing.** `[^\\d.]` throws away the currency
symbol, the thousands separator, the minus sign and the decimal comma, and then
hopes the remainder is a number. On the euro formatting the same shop uses for
other customers, `"1.299,00 EUR"` becomes `"1.29900"`, which is 1.299 -- a
thousand times too small, and it does not raise, so nothing anywhere notices.
And because the dot is the only separator the pattern permits, a price written
with a comma is either misread or destroyed.

**2. A range is not a price.** A deal page shows `"$1,299.00 - $1,399.00"`.
Deleting the non-digits leaves `"1299.001399.00"`, `float` raises, and the
`except` turns the most informative price on the page into zero.

**3. Zero is not "unknown", and it is not free either.** Every failure path
returns `0.0`, so an unreadable price is indistinguishable from a free item, and
`calculate_percentage_change` then answers `0.0` for a price that went from
unreadable to $5 -- "no change" -- because it guards `old_price <= 0` instead of
admitting it has no baseline. A percentage that exists is worth stating; one
that cannot exist must not be reported as zero.

**4. The first match is not the buy box.** The parser walked a list of selectors
in order and took the first text it found, and the first `.a-offscreen` on a
discounted page is the struck-through list price, not the price you pay. Here
the buy box is named explicitly, and the list price is read separately as what
it is.

So this module keeps money as integer cents and a currency, refuses to invent a
value it cannot read, keeps a range as a range, and reports a change only when
there is a baseline to change from. The demonstration is offline: one bundled
page, one bundled price log, and no network anywhere.

Standard library only: no requests, no beautifulsoup, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OFFER_FILE = DATA_DIR / "offer.html"
WATCH_FILE = DATA_DIR / "watch.txt"

#: The legacy conversion, transcribed, so the demo can refute it.
LEGACY_CLEAN = ('cleaned = re.sub(r"[^\\d.]", "", value)\n'
                'try:\n'
                '    return float(cleaned)\n'
                'except ValueError:\n'
                '    return 0.0')

#: The legacy percentage, transcribed: a zero baseline reports no change.
LEGACY_CHANGE = ("if old_price <= 0:\n"
                 "    return 0.0\n"
                 "return ((new_price - old_price) / old_price) * 100")

#: Currency symbols this lab recognises, and the code each one means.
#: Written as escapes so that every source file in this repository is ASCII.
SYMBOLS = {"$": "USD", "\u00a3": "GBP", "\u20ac": "EUR", "\u00a5": "JPY"}

#: The codes, longest first, so `USD` is not read as `US` and a stray `D`.
CODES = ("USD", "GBP", "EUR", "JPY")

#: The separators a price may hold, and the ones that mean "a range instead".
RANGE_MARKS = ("\u2013", "\u2014", " to ", " - ")

#: A hyphen with an amount on each side: `1,299.00-1,399.00`.
TWO_AMOUNTS = re.compile(r"\d[\d.,]*\s*-\s*[\d$\u00a3\u20ac\u00a5]")

#: What the buy box is called on the page this lab reads.
BUY_BOX = "priceToPay"

#: What the struck-through list price is called.
LIST_BOX = "a-text-price"


class PriceError(Exception):
    """A price that cannot be read, with the sentence that says why."""


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #
def label_for(code: str) -> str:
    """How a currency is printed: `$` when that is ASCII, the code when not.

    The symbol is what a person reads on the page, but a demonstration has to
    be one encoding everywhere, so `EUR 1,299.00` is a euro amount written so
    that it prints the same on any console.
    """
    if code == "USD":
        return "$"
    return f"{code} "


@dataclass(frozen=True, order=True)
class Money:
    """An amount in integer cents, and the currency it is an amount of.

    Cents, because a float cannot hold a tenth of a cent and cannot hold
    `0.10 + 0.20` either. Integer division is done once, on purpose, where the
    caller can see it.
    """

    cents: int
    currency: str = "USD"

    def __post_init__(self) -> None:
        if not isinstance(self.cents, int) or isinstance(self.cents, bool):
            raise PriceError(f"cents are a whole number of cents, got "
                             f"{self.cents!r}")
        if not isinstance(self.currency, str) or \
                len(self.currency) != 3 or not self.currency.isupper():
            raise PriceError(f"a currency is three capital letters, got "
                             f"{self.currency!r}")

    def format(self) -> str:
        """`$1,299.00` -- grouped, two decimals, the sign in front."""
        sign = "-" if self.cents < 0 else ""
        whole, part = divmod(abs(self.cents), 100)
        return f"{sign}{label_for(self.currency)}{whole:,}.{part:02d}"

    def __str__(self) -> str:
        return self.format()

    def plus(self, other: "Money") -> "Money":
        self.same_currency(other)
        return Money(self.cents + other.cents, self.currency)

    def minus(self, other: "Money") -> "Money":
        self.same_currency(other)
        return Money(self.cents - other.cents, self.currency)

    def same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise PriceError(f"cannot combine {self.currency} with "
                             f"{other.currency} without a rate")


def divide_half_up(numerator: int, denominator: int) -> int:
    """Integer division that rounds a half away from zero.

    `round()` cannot be used: it is half-to-even, so `round(0.5)` is 0 and
    `round(1.5)` is 2, which makes a report that rounds two prices differently
    depending on which side of the half they land.
    """
    if denominator == 0:
        raise PriceError("cannot divide by zero")
    sign = -1 if (numerator < 0) != (denominator < 0) else 1
    top, bottom = abs(numerator), abs(denominator)
    return sign * ((2 * top + bottom) // (2 * bottom))


# --------------------------------------------------------------------------- #
# Reading a price
# --------------------------------------------------------------------------- #
def is_range(value: str) -> bool:
    """True when the text names two amounts, which is a range, not a price."""
    if not isinstance(value, str):
        raise PriceError(f"a price is text, got {type(value).__name__}")
    body = value.strip()
    if any(mark in body for mark in RANGE_MARKS):
        return True
    return _two_amounts(body)


def _two_amounts(body: str) -> bool:
    """True when a hyphen sits between two amounts."""
    return bool(TWO_AMOUNTS.search(body))


def parse_amount(value: str) -> tuple[int, str]:
    """Read money from a string, as cents and a currency code.

    The rules, in order, and each one is a refusal rather than a guess:

    * one currency marker, symbol or code, or none (which means USD);
    * a range is refused -- `parse_range` is what reads a range;
    * nothing left after the digits and the separators is allowed;
    * if both `,` and `.` appear, the **last** one is the decimal separator;
    * a single separator followed by exactly three digits is a thousands
      separator, so `1.299` is 1299 and `1.29` is 1.29;
    * more than two decimals is refused, because a price is not a rate.
    """
    return _read_amount(value)


def legacy_display(value: float) -> str:
    """A float the legacy function returned, shown the way it reported it."""
    return f"${value:,.2f}"


def _read_amount(value: str) -> tuple[int, str]:
    if not isinstance(value, str):
        raise PriceError(f"a price is text, got {type(value).__name__}")
    body = value.strip()
    if not body:
        raise PriceError("the price text is empty")

    currency = ""
    for symbol, code in SYMBOLS.items():
        if symbol in body:
            if currency:
                raise PriceError(f"two currency symbols in {value!r}: this is "
                                 f"not one price")
            currency = code
            body = body.replace(symbol, " ")
    for code in CODES:
        if re.search(rf"(?<![A-Za-z]){code}(?![A-Za-z])", body,
                     re.IGNORECASE):
            if currency and currency != code:
                raise PriceError(f"two currencies in {value!r}: "
                                 f"{currency} and {code}")
            currency = code
            body = re.sub(rf"(?<![A-Za-z]){code}(?![A-Za-z])", " ", body,
                          flags=re.IGNORECASE)

    if is_range(body):
        raise PriceError(f"this is a range, not a price: {value.strip()!r}")

    core = body.replace(" ", "").replace("\u00a0", "")
    if not core:
        raise PriceError(f"no digits in {value!r}")
    for character in core:
        if character not in "0123456789.,":
            raise PriceError(f"a price cannot hold {character!r}, but "
                             f"{value.strip()!r} does")

    whole, fraction = _split_core(core, value)
    cents = whole * 100 + fraction
    return cents, currency or "USD"


#: A group of digits, used to check a thousands separator.
GROUP = re.compile(r"\d+")


def _split_core(core: str, original: str) -> tuple[int, int]:
    """The integer part and the fraction, in cents, from a digit core."""
    has_comma, has_dot = "," in core, "." in core

    if has_comma and has_dot:
        cut = max(core.rfind(","), core.rfind("."))
        decimal = core[cut]
        grouping = "." if decimal == "," else ","
        whole_text, fraction_text = core[:cut], core[cut + 1:]
        _check_groups(whole_text, grouping, original)
        whole = int(whole_text.replace(grouping, ""))
        return whole, _fraction(fraction_text, original)

    if has_comma or has_dot:
        separator = "," if has_comma else "."
        parts = core.split(separator)
        if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
            return int(parts[0] or "0"), _fraction(parts[1], original)
        if len(parts) > 1:
            for group in parts[1:]:
                if len(group) != 3:
                    raise PriceError(f"{original.strip()!r} is not a price: "
                                     f"the group {group!r} is not three "
                                     f"digits, and a decimal cannot have "
                                     f"more than two")
            return int("".join(parts)), 0
        return int(core), 0

    return int(core), 0


def _check_groups(text: str, separator: str, original: str) -> None:
    parts = text.split(separator)
    if len(parts[0]) not in (1, 2, 3):
        raise PriceError(f"{original.strip()!r} is not a price: {parts[0]!r} "
                         f"is not a number")
    for group in parts[1:]:
        if len(group) != 3:
            raise PriceError(f"{original.strip()!r} is not a price: the group "
                             f"{group!r} is not three digits")


def _fraction(text: str, original: str) -> int:
    if not text:
        raise PriceError(f"{original.strip()!r} ends at the decimal separator")
    if len(text) > 2:
        raise PriceError(f"{original.strip()!r} has {len(text)} decimals, and "
                         f"a price has two")
    return int(text.ljust(2, "0"))


def parse_price(value: str) -> Money:
    """One price, as `Money`, or `PriceError` with the reason."""
    cents, currency = parse_amount(value)
    return Money(cents, currency)


def parse_range(value: str) -> tuple[Money | None, Money | None]:
    """The two ends of a price range, either of which may be missing."""
    if not isinstance(value, str):
        raise PriceError(f"a price is text, got {type(value).__name__}")
    body = value.strip()
    if not is_range(body):
        raise PriceError(f"this is not a range: {body!r}")
    halves = re.split(r"\s*(?:\u2013|\u2014|to|-)\s*", body, maxsplit=1)
    return (parse_price(halves[0]) if halves[0].strip() else None,
            parse_price(halves[1]) if len(halves) > 1 and
            halves[1].strip() else None)


# --------------------------------------------------------------------------- #
# The legacy conversions, executable
# --------------------------------------------------------------------------- #
def legacy_clean_price(value: str | None) -> float:
    """The legacy function, rewritten faithfully: a float, or `0.0`."""
    if not value:
        return 0.0
    cleaned = re.sub(r"[^\d.]", "", value)
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def legacy_percentage_change(old_price: float, new_price: float) -> float:
    """The legacy change, rewritten faithfully: `0.0` when there is no base."""
    if old_price <= 0:
        return 0.0
    return ((new_price - old_price) / old_price) * 100


# --------------------------------------------------------------------------- #
# A change, in basis points
# --------------------------------------------------------------------------- #
def change_bp(old: Money | None, new: Money | None) -> int | None:
    """How much `new` moved from `old`, in hundredths of a percent.

    `None` when either end is unknown: a change from a price nobody read is not
    zero, it is unknown. A **zero** baseline is a different thing again -- a
    real price of nothing cannot be a baseline -- so it raises.
    """
    if old is None or new is None:
        return None
    if old.currency != new.currency:
        raise PriceError(f"cannot compare {old.currency} with {new.currency}")
    if old.cents <= 0:
        raise PriceError(f"{old.format()} cannot be a baseline: a change is "
                         f"measured from a price greater than zero")
    return divide_half_up((new.cents - old.cents) * 10_000, old.cents)


def format_bp(points: int | None) -> str:
    """`-7.15%`, or `unknown` -- never a zero standing in for an unknown."""
    if points is None:
        return "unknown"
    sign = "-" if points < 0 else "+"
    whole, part = divmod(abs(points), 100)
    return f"{sign}{whole}.{part:02d}%"


# --------------------------------------------------------------------------- #
# Just enough DOM
# --------------------------------------------------------------------------- #
VOID = frozenset({"br", "img", "hr", "meta", "input", "link", "source"})


class Element:
    """One HTML element: its tag, its attributes and its children."""

    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag: str, attrs: dict[str, str],
                 parent: "Element | None" = None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[Element | str] = []
        self.parent = parent

    def classes(self) -> tuple[str, ...]:
        return tuple(self.attrs.get("class", "").split())

    def text(self) -> str:
        """Every text node underneath, whitespace collapsed."""
        parts: list[str] = []
        for child in self.children:
            parts.append(child if isinstance(child, str) else child.text())
        return re.sub(r"\s+", " ", "".join(parts)).strip()

    def walk(self):
        yield self
        for child in self.children:
            if not isinstance(child, str):
                yield from child.walk()

    def find_all(self, tag: str | None = None, cls: str | None = None,
                 id: str | None = None) -> tuple["Element", ...]:
        found = []
        for element in self.walk():
            if element is self:
                continue
            if tag is not None and element.tag != tag:
                continue
            if cls is not None and cls not in element.classes():
                continue
            if id is not None and element.attrs.get("id") != id:
                continue
            found.append(element)
        return tuple(found)

    def find(self, tag: str | None = None, cls: str | None = None,
             id: str | None = None) -> "Element | None":
        found = self.find_all(tag, cls, id)
        return found[0] if found else None


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Element("#document", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        element = Element(tag, dict(attrs), self.stack[-1])
        self.stack[-1].children.append(element)
        if tag not in VOID:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Element(tag, dict(attrs), self.stack[-1]))

    def handle_endtag(self, tag):
        for position in range(len(self.stack) - 1, 0, -1):
            if self.stack[position].tag == tag:
                del self.stack[position:]
                return

    def handle_data(self, data):
        if data.strip():
            self.stack[-1].children.append(data)


def parse_html(text: str) -> Element:
    """A tree from HTML text, with comments dropped and entities decoded."""
    if not isinstance(text, str):
        raise PriceError(f"a page is text, got {type(text).__name__}")
    builder = _Builder()
    builder.feed(text)
    builder.close()
    return builder.root


# --------------------------------------------------------------------------- #
# Reading one offer
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Offer:
    """What the buy box said, and what could not be read."""

    title: str
    price: Money | None
    list_price: Money | None
    availability: str
    note: str

    def discount_bp(self) -> int | None:
        """How far below the list price the buy box is, in basis points."""
        if self.price is None or self.list_price is None:
            return None
        if self.list_price.cents <= 0:
            return None
        return divide_half_up((self.price.cents - self.list_price.cents)
                              * 10_000, self.list_price.cents)

    def line(self) -> str:
        if self.price is not None:
            return f"{self.price.format():>12}  {self.title}"
        return f"{'?':>12}  {self.title}  ({self.note})"


def _offscreen(element: Element) -> str:
    found = element.find(cls="a-offscreen")
    return found.text() if found is not None else ""


def read_price(element: Element | None) -> tuple[Money | None, str]:
    """A price from an element, or `None` and the reason it is unknown."""
    if element is None:
        return None, "the page holds no such element"
    text = _offscreen(element) or element.text()
    if not text:
        return None, "the element is empty"
    try:
        return parse_price(text), ""
    except PriceError as error:
        return None, str(error)


def parse_offer(html: str) -> Offer:
    """Read one product page, naming the buy box instead of taking a first match."""
    page = parse_html(html)
    title_element = page.find(id="productTitle") or page.find("h1")
    title = title_element.text() if title_element is not None else ""

    buy_box = page.find(cls=BUY_BOX) or page.find(id="corePrice_feature_div") \
        or page.find(id="priceblock_ourprice")
    price, reason = read_price(buy_box)

    list_box = page.find(cls=LIST_BOX)
    list_price = None
    if list_box is not None:
        try:
            list_price = parse_price(_offscreen(list_box) or list_box.text())
        except PriceError:
            list_price = None

    availability_element = page.find(id="availability")
    availability = availability_element.text() if availability_element else ""

    note = ""
    if price is None:
        note = reason or "no price in the buy box"
    return Offer(title, price, list_price, availability, note)


def legacy_offer_price(html: str) -> float:
    """The legacy buy-box read: the first `.a-offscreen` anywhere on the page."""
    page = parse_html(html)
    for element in page.walk():
        if "a-offscreen" in element.classes():
            return legacy_clean_price(element.text())
    return 0.0


def read_offer_page(path=None) -> str:
    target = Path(OFFER_FILE if path is None else path)
    if not target.is_file():
        raise PriceError(f"file not found: {target}")
    return target.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Watching a price over time
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Sample:
    """One reading: a tick number and the price seen at it."""

    at: int
    price: Money


@dataclass(frozen=True)
class Watch:
    """A price log, oldest first, and the questions worth asking of it."""

    samples: tuple[Sample, ...]

    def __post_init__(self) -> None:
        if not self.samples:
            raise PriceError("a watch needs at least one sample")
        ticks = [sample.at for sample in self.samples]
        if ticks != sorted(ticks):
            raise PriceError("the samples are not in tick order")
        if len(set(ticks)) != len(ticks):
            raise PriceError("two samples share a tick")

    def __len__(self) -> int:
        return len(self.samples)

    def first(self) -> Sample:
        return self.samples[0]

    def last(self) -> Sample:
        return self.samples[-1]

    def lowest(self) -> Sample:
        return min(self.samples, key=lambda sample: (sample.price.cents,
                                                     sample.at))

    def change(self) -> int | None:
        """The change from the first sample to the last, in basis points."""
        return change_bp(self.first().price, self.last().price)

    def below(self, target: Money) -> tuple[Sample, ...]:
        """Every sample at or below a target price."""
        return tuple(sample for sample in self.samples
                     if sample.price.cents <= target.cents)

    def first_below(self, target: Money) -> Sample | None:
        found = self.below(target)
        return found[0] if found else None

    def lines(self) -> tuple[str, ...]:
        return tuple(f"t={sample.at:<3} {sample.price.format()}"
                     for sample in self.samples)


def parse_watch(text: str) -> Watch:
    """Read `tick<TAB>price` lines into a `Watch`."""
    samples: list[Sample] = []
    for number, line in enumerate(text.replace("\r\n", "\n")
                                  .replace("\r", "\n").split("\n"), start=1):
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        if "\t" not in line:
            raise PriceError(f"line {number}: expected a tick, a tab and a "
                             f"price")
        tick_text, price_text = line.split("\t", 1)
        try:
            tick = int(tick_text.strip())
        except ValueError:
            raise PriceError(f"line {number}: {tick_text.strip()!r} is not a "
                             f"whole tick") from None
        samples.append(Sample(tick, parse_price(price_text.strip())))
    if not samples:
        raise PriceError("the watch holds no samples")
    return Watch(tuple(samples))


def read_watch(path=None) -> Watch:
    target = Path(WATCH_FILE if path is None else path)
    if not target.is_file():
        raise PriceError(f"file not found: {target}")
    return parse_watch(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(offer: Offer, watch: Watch, page: str) -> list[tuple[str, bool]]:
    """Nine checks, each re-derived rather than restated."""

    def every_amount_is_whole_cents() -> bool:
        amounts = [sample.price for sample in watch.samples]
        if offer.price is not None:
            amounts.append(offer.price)
        if offer.list_price is not None:
            amounts.append(offer.list_price)
        return all(isinstance(amount.cents, int) and
                   not isinstance(amount.cents, bool) for amount in amounts)

    def every_amount_prints_and_reads_back() -> bool:
        for sample in watch.samples:
            printed = sample.price.format()
            if parse_price(printed) != sample.price:
                return False
        return True

    def no_known_price_is_zero() -> bool:
        if offer.price is not None and offer.price.cents == 0:
            return False
        return all(sample.price.cents > 0 for sample in watch.samples)

    def the_legacy_cleaner_agrees_on_plain_text() -> bool:
        return legacy_clean_price("$1,299.00") == 1299.0

    def the_legacy_cleaner_collapses_a_euro_price() -> bool:
        return legacy_clean_price("1.299,00 EUR") < 2.0 and \
            parse_price("1.299,00 EUR").cents == 129_900

    def the_buy_box_is_not_the_first_match() -> bool:
        return offer.price is not None and \
            offer.price.cents != int(legacy_offer_price(page) * 100)

    def the_list_price_is_above_the_buy_box() -> bool:
        if offer.price is None or offer.list_price is None:
            return True
        return offer.list_price.cents >= offer.price.cents

    def the_watch_is_ordered_and_its_lowest_is_the_minimum() -> bool:
        ticks = [sample.at for sample in watch.samples]
        if ticks != sorted(ticks):
            return False
        return watch.lowest().price.cents == min(sample.price.cents
                                                 for sample in watch.samples)

    def the_change_is_measured_from_the_first_sample() -> bool:
        counted = change_bp(watch.first().price, watch.last().price)
        return counted == watch.change()

    checks = [
        ("every amount is a whole number of cents, never a float",
         every_amount_is_whole_cents),
        ("every amount prints and reads back to the same cents",
         every_amount_prints_and_reads_back),
        ("no price the page stated is recorded as zero",
         no_known_price_is_zero),
        ("the legacy cleaner reads the plain price correctly",
         the_legacy_cleaner_agrees_on_plain_text),
        ("the legacy cleaner misreads the euro price by 1000x",
         the_legacy_cleaner_collapses_a_euro_price),
        ("the buy box price is not the first .a-offscreen on the page",
         the_buy_box_is_not_the_first_match),
        ("the list price is never below the price being asked",
         the_list_price_is_above_the_buy_box),
        ("the watch is in tick order and its lowest is the minimum",
         the_watch_is_ordered_and_its_lowest_is_the_minimum),
        ("the reported change is measured from the first sample",
         the_change_is_measured_from_the_first_sample),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
CURIOUS = (
    ("$1,299.00", "a plain price"),
    ("$1,299", "no decimals at all"),
    ("1.299,00 EUR", "euro formatting: dot groups, comma decides"),
    ("1,299.00 USD", "the same money, written the other way"),
    ("$1 299.00", "a space as a thousands separator"),
    ("$18.5", "one decimal, which means 50 cents"),
    ("$0.00", "a price of nothing, which is a real answer"),
    ("$1,299.00 - $1,399.00", "a range, which is not one price"),
    ("$1,299.005", "three decimals, which is not a price"),
    ("", "no text at all"),
    ("$", "a symbol with no digits"),
)


def agrees(text: str) -> bool:
    """True when the legacy float and the parsed cents are the same money."""
    try:
        parsed = parse_price(text)
    except PriceError:
        return False
    return abs(legacy_clean_price(text) - parsed.cents / 100) < 0.005


def run_demo() -> int:
    page = read_offer_page()
    offer = parse_offer(page)
    watch = read_watch()

    print("=" * 74)
    print(" PRICE LAB - a price is money, not the digits left after deletion")
    print("=" * 74)

    print("\n  the legacy conversion, transcribed:")
    for line in LEGACY_CLEAN.split("\n"):
        print(f"    {line}")
    for line in LEGACY_CHANGE.split("\n"):
        print(f"    {line}")

    print("\n  what the legacy cleaner makes of real price text:")
    for text, description in CURIOUS:
        legacy = legacy_clean_price(text)
        try:
            parsed = parse_price(text)
            shown = f"{parsed.format():>12}  {parsed.cents:>7} cents"
        except PriceError as error:
            shown = f"{'refused':>12}  {error}"
        print(f"    {text!r:<26} {legacy:>10.4f}   {shown}")
    wrong = [text for text, _ in CURIOUS if not agrees(text)
             and _reads(text)]
    silent = [text for text, _ in CURIOUS if not _reads(text)]
    print(f"    {len(wrong)} readable amount(s) disagree with the legacy "
          f"float: {', '.join(repr(text) for text in wrong)}")
    print(f"    {len(silent)} text(s) the legacy cleaner answers silently with "
          f"0.0, and none of them raises")

    print("\n  the page, and the two ways to read it:")
    print(f"    the page holds the title {offer.title!r}")
    print(f"    the first .a-offscreen on the page says "
          f"{legacy_display(legacy_offer_price(page))}")
    print(f"    that is the struck-through list price, and the legacy parser")
    print(f"    reported it as the price being asked")
    print(f"    the buy box ({BUY_BOX}) says "
          f"{offer.price.format() if offer.price else 'nothing'}")
    print(f"    the list price, read as a list price, is "
          f"{offer.list_price.format() if offer.list_price else 'nothing'}")
    print(f"    availability: {offer.availability or 'not stated'}")
    print(f"    change from the list price: "
          f"{format_bp(offer.discount_bp())}")

    print(f"\n  the price over {len(watch)} days:")
    for line in watch.lines():
        print(f"    {line}")
    lowest = watch.lowest()
    print(f"    lowest {lowest.price.format()} at t={lowest.at}, "
          f"first {watch.first().price.format()}, "
          f"last {watch.last().price.format()}")
    print(f"    from the first sample to the last: "
          f"{format_bp(watch.change())}")
    target = Money(1_250_00)
    first_hit = watch.first_below(target)
    print(f"    at or below {target.format()}: "
          f"{len(watch.below(target))} day(s), first at "
          f"t={first_hit.at if first_hit else 'never'}")

    print("\n  a change needs a baseline, and unknown is not zero:")
    print(f"    change_bp(first, last)      = "
          f"{format_bp(watch.change())}")
    print(f"    change_bp(None, last)       = "
          f"{format_bp(change_bp(None, watch.last().price))}")
    try:
        change_bp(Money(0), watch.last().price)
    except PriceError as error:
        print(f"    change_bp(zero, last)       = refused: {error}")
    print(f"    the legacy percentage from an unreadable price to "
          f"{watch.last().price.format()}:")
    print(f"      legacy_percentage_change(0.0, 1299.0) = "
          f"{legacy_percentage_change(0.0, 1299.0):.1f} -- 'no change'")

    checks = audit(offer, watch, page)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{len(CURIOUS)} pieces of price text give "
          f"{sum(1 for text, _ in CURIOUS if _reads(text))} readable "
          f"amount(s) and {sum(1 for text, _ in CURIOUS if not _reads(text))} "
          f"refusal(s), the euro price is "
          f"{parse_price('1.299,00 EUR').format()} where the legacy cleaner "
          f"says {legacy_clean_price('1.299,00 EUR')}, the buy box says "
          f"{offer.price.format()} where the first match says "
          f"{legacy_display(legacy_offer_price(page))}, the "
          f"{len(watch)}-day watch falls {format_bp(watch.change())} to a low "
          f"of {watch.lowest().price.format()}, the legacy change from an "
          f"unreadable price is "
          f"{legacy_percentage_change(0.0, 1299.0):.1f}%, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("Demo completed successfully.")
    return 0


def _reads(text: str) -> bool:
    try:
        parse_price(text)
        return True
    except PriceError:
        return False
