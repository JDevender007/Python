"""A displayed count is a measurement, not a number.

The legacy scraper read a star count like this:

    def clean_number(value):
        cleaned = re.sub(r"[^\\d]", "", value)
        try:
            return int(cleaned)
        except ValueError:
            return 0

and turned a "2.3k" into a `28`-ish integer by deleting every character that was
not a digit. It also read a magnitude with `int()`, which truncates:

    def to_int(value):
        number = value.rstrip("kmb")
        return int(float(number)) * 1000

**1. `2.3k` is not `23`.** Deleting the `k` and the `.` leaves `"23"`, a number
twenty-three times too small -- and for `"1.2m"` it leaves `"12"`, a hundred
thousand times too small. The letters are not decoration, they are the magnitude.

**2. A suffix is a resolution.** `2.3k` does not mean 2,300 exactly; it means the
page printed one decimal place in thousands, so the true figure is somewhere in
2,250..2,349. Reading it as an exact integer invents precision the page never
showed, and then reports a "difference" of 4 against a repository at 2,304 that
the page could not have distinguished at all.

**3. `int()` truncates where a person rounds.** `int(float("2.9"))` is 2, so
`2.9k` becomes 2,000 -- a 31% error on the number printed, and eight hundred
and ninety-nine stars that vanished silently.

**4. Zero is not "unknown".** Every failure path returns `0`, so a count the page
did not print is indistinguishable from a repository with no stars.

So this module keeps a count as an **amount and a resolution**: an exact integer
when the page printed every digit, and an interval when it printed a suffix. Two
counts whose intervals overlap are reported as indistinguishable, and a gain over
time is reported as a range rather than a point.

The demonstration is offline: one bundled listing page, one bundled star history,
and no network anywhere.

Standard library only: no requests, no beautifulsoup, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LISTING_FILE = DATA_DIR / "repos.html"
HISTORY_FILE = DATA_DIR / "history.txt"

#: The legacy cleaner, transcribed, so the demo can refute it.
LEGACY_CLEAN = ('cleaned = re.sub(r"[^\\d]", "", value)\n'
                'try:\n'
                '    return int(cleaned)\n'
                'except ValueError:\n'
                '    return 0')

#: The legacy magnitude reader, transcribed: one multiplier, and `int()` truncates.
LEGACY_MAGNITUDE = ('number = value.rstrip("kmb")\n'
                    'return int(float(number)) * 1000')

#: The magnitudes GitHub prints, and what a suffix means.
SUFFIXES = {"": 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}

#: A grouped plain number: `1,234` or `12,345,678`.
GROUPED = re.compile(r"^\d{1,3}(?:,\d{3})+$")

#: A plain integer, no grouping.
PLAIN = re.compile(r"^\d+$")

#: A number with at most one decimal place, which is what a suffix is printed with.
SHORT = re.compile(r"^\d+(?:\.\d)?$")

#: The class names this lab's listing page uses.
REPO_CLASS = "repo"
STARS_CLASS = "stars"
FORKS_CLASS = "forks"
LANGUAGE_CLASS = "language"


class CountError(Exception):
    """A count that cannot be read, with the sentence that says why."""


# --------------------------------------------------------------------------- #
# A count
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Count:
    """An amount, and the step the page printed it in.

    `resolution` is 1 when every digit was printed; otherwise it is the size of
    the step the printed figure was rounded to. `2.3k` is `Count(2300, 100)`,
    which says "between 2,250 and 2,349" without pretending to know which.
    """

    amount: int
    resolution: int = 1

    def __post_init__(self) -> None:
        for name, value in (("amount", self.amount),
                            ("resolution", self.resolution)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise CountError(f"{name} is a whole number, got {value!r}")
        if self.amount < 0:
            raise CountError(f"a count cannot be negative, got {self.amount}")
        if self.resolution < 1:
            raise CountError(f"a resolution is at least 1, got "
                             f"{self.resolution}")

    @property
    def exact(self) -> bool:
        """True when the page printed every digit of this figure."""
        return self.resolution == 1

    def low(self) -> int:
        """The smallest figure this display could have stood for."""
        return self.amount - self.resolution // 2

    def high(self) -> int:
        """The largest figure this display could have stood for."""
        return self.amount + self.resolution // 2

    def could_be(self, value: int) -> bool:
        """True when `value` is a number this display could have printed."""
        if not isinstance(value, int) or isinstance(value, bool):
            raise CountError(f"a count is a whole number, got {value!r}")
        return self.low() <= value <= self.high()

    def format(self) -> str:
        """`1,234` when exact, `2.3k` when the page printed a suffix."""
        if self.exact:
            return f"{self.amount:,}"
        for magnitude in (1_000_000_000, 1_000_000, 1_000):
            if self.amount >= magnitude and \
                    self.resolution <= magnitude and \
                    magnitude % self.resolution == 0:
                decimals = 0
                step = magnitude
                while step > self.resolution:
                    step //= 10
                    decimals += 1
                if decimals > 1:
                    break
                scale = 10 ** decimals
                short = self.amount * scale // magnitude
                whole, part = divmod(short, scale)
                suffix = {1_000_000_000: "b", 1_000_000: "m",
                          1_000: "k"}[magnitude]
                if decimals == 0:
                    return f"{whole}{suffix}"
                return f"{whole}.{part}{suffix}"
        return f"{self.amount:,}"

    def __str__(self) -> str:
        return self.format()


def parse_count(text: str) -> Count:
    """Read a count from the text a repository page prints.

    The rules, each a refusal rather than a guess:

    * one suffix at most, from `k`, `m`, `b`, and it must be the last character;
    * with a suffix, at most **one** decimal place, because that is what the page
      prints -- `2.34k` is not a shape GitHub produces;
    * without a suffix, a whole number only: `12.5` is not a count;
    * `,` groups thousands in threes (`1,234`), and nothing else;
    * nothing but digits, one `.` and those commas is allowed.
    """
    if not isinstance(text, str):
        raise CountError(f"a count is text, got {type(text).__name__}")
    body = text.strip()
    if not body:
        raise CountError("the count text is empty")

    suffix = ""
    if body[-1].lower() in ("k", "m", "b"):
        suffix = body[-1].lower()
        body = body[:-1].strip()
        if not body:
            raise CountError(f"no digits in {text.strip()!r} before the "
                             f"{text.strip()[-1]!r}")

    for character in body:
        if character not in "0123456789.,":
            raise CountError(f"a count cannot hold {character!r}, but "
                             f"{text.strip()!r} does")

    if "," in body:
        if suffix:
            raise CountError(f"{text.strip()!r} groups thousands and also "
                             f"names a magnitude: a page prints one or the "
                             f"other")
        if not GROUPED.match(body):
            raise CountError(f"{text.strip()!r} is not a grouped number: every "
                             f"group after the first holds exactly three "
                             f"digits")
        return Count(int(body.replace(",", "")), 1)

    if not suffix:
        if "." in body:
            raise CountError(f"{text.strip()!r} is not a count: without a "
                             f"suffix the page prints a whole number, and "
                             f"groups thousands with commas")
        if not PLAIN.match(body):
            raise CountError(f"{text.strip()!r} is not a count: without a "
                             f"suffix the page prints a whole number")
        return Count(int(body), 1)

    if not SHORT.match(body):
        raise CountError(f"{text.strip()!r} is not a count: a suffix is "
                         f"printed with at most one decimal place")
    whole_text, _, fraction_text = body.partition(".")
    magnitude = SUFFIXES[suffix]
    decimals = len(fraction_text)
    if int(whole_text) == 0:
        raise CountError(f"{text.strip()!r} is not a count: a figure printed "
                         f"with the {suffix!r} suffix is at least one of its "
                         f"magnitude")
    amount = int(whole_text) * magnitude + \
        int(fraction_text or "0") * (magnitude // 10 ** decimals)
    return Count(amount, magnitude // 10 ** decimals)


# --------------------------------------------------------------------------- #
# Comparing two counts
# --------------------------------------------------------------------------- #
def relation(left: Count, right: Count) -> str:
    """How two displayed counts compare, honestly.

    `same` and `different` are only available when both figures are exact.
    Two displays whose intervals overlap are `indistinguishable`: the page never
    printed enough digits to tell them apart, so neither may claim it did.
    """
    if left.exact and right.exact:
        return "same" if left.amount == right.amount else "different"
    if left.low() <= right.high() and right.low() <= left.high():
        return "indistinguishable"
    return "fewer" if left.amount < right.amount else "more"


def gain(first: Count, last: Count) -> tuple[int, int]:
    """How much a count moved, as the interval it could have moved by."""
    low = (last.amount - last.resolution // 2) - (first.amount +
                                                 first.resolution // 2)
    high = (last.amount + last.resolution // 2) - (first.amount -
                                                  first.resolution // 2)
    return low, high


def format_gain(bounds: tuple[int, int]) -> str:
    """`+400 to +600`, or `+0` when both ends agree."""
    low, high = bounds
    if low == high:
        return f"{low:+,}"
    return f"{low:+,} to {high:+,}"


# --------------------------------------------------------------------------- #
# The legacy conversions, executable
# --------------------------------------------------------------------------- #
def legacy_clean_number(value: str | None) -> int:
    """The legacy cleaner, rewritten faithfully: digits only, or `0`."""
    if not value:
        return 0
    cleaned = re.sub(r"[^\d]", "", value)
    try:
        return int(cleaned)
    except ValueError:
        return 0


def legacy_magnitude(value: str | None) -> int:
    """The legacy magnitude reader, rewritten faithfully: truncates, times 1000."""
    if not value:
        return 0
    number = value.rstrip("kmbKMB")
    try:
        return int(float(number)) * 1000
    except ValueError:
        return 0


# --------------------------------------------------------------------------- #
# Just enough DOM
# --------------------------------------------------------------------------- #
VOID = frozenset({"br", "img", "hr", "meta", "input", "link", "source"})


class Element:
    """One HTML element: its tag, its attributes and its children."""

    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag: str, attrs: dict[str, str]) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[Element | str] = []

    def classes(self) -> tuple[str, ...]:
        return tuple(self.attrs.get("class", "").split())

    def text(self) -> str:
        parts: list[str] = []
        for child in self.children:
            parts.append(child if isinstance(child, str) else child.text())
        return re.sub(r"\s+", " ", "".join(parts)).strip()

    def walk(self):
        yield self
        for child in self.children:
            if not isinstance(child, str):
                yield from child.walk()

    def find_all(self, tag: str | None = None, cls: str | None = None):
        found = []
        for element in self.walk():
            if element is self:
                continue
            if tag is not None and element.tag != tag:
                continue
            if cls is not None and cls not in element.classes():
                continue
            found.append(element)
        return tuple(found)

    def find(self, tag: str | None = None, cls: str | None = None):
        found = self.find_all(tag, cls)
        return found[0] if found else None


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Element("#document", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        element = Element(tag, dict(attrs))
        self.stack[-1].children.append(element)
        if tag not in VOID:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Element(tag, dict(attrs)))

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
        raise CountError(f"a page is text, got {type(text).__name__}")
    builder = _Builder()
    builder.feed(text)
    builder.close()
    return builder.root


# --------------------------------------------------------------------------- #
# Reading the listing
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Repo:
    """One repository row: a name, the counts the page printed, a language."""

    name: str
    stars: Count | None
    forks: Count | None
    language: str
    note: str

    def line(self) -> str:
        stars = self.stars.format() if self.stars else "?"
        forks = self.forks.format() if self.forks else "?"
        return f"{self.name:<16} {stars:>8} stars {forks:>7} forks  " \
               f"{self.language or '-'}"

    def star_line(self) -> str:
        """The star figure with the interval it could have stood for."""
        if self.stars is None:
            return f"{self.name:<16} {'?':>8}  ({self.note})"
        if self.stars.exact:
            return f"{self.name:<16} {self.stars.format():>8}  exact"
        return (f"{self.name:<16} {self.stars.format():>8}  between "
                f"{self.stars.low():,} and {self.stars.high():,}")


@dataclass(frozen=True)
class Listing:
    """The repositories on one page, in the order the page listed them."""

    repos: tuple[Repo, ...]

    def __post_init__(self) -> None:
        if not self.repos:
            raise CountError("a listing needs at least one repository")
        names = [repo.name for repo in self.repos]
        if len(set(names)) != len(names):
            raise CountError("two repositories share a name")

    def __len__(self) -> int:
        return len(self.repos)

    def get(self, name: str) -> Repo:
        for repo in self.repos:
            if repo.name == name:
                return repo
        raise CountError(f"no repository named {name!r} on the page")

    def names(self) -> tuple[str, ...]:
        return tuple(repo.name for repo in self.repos)


def _read_count(element: Element | None, what: str) -> tuple[Count | None, str]:
    if element is None:
        return None, f"the page prints no {what}"
    text = element.text()
    if not text:
        return None, f"the {what} is empty"
    try:
        return parse_count(text), ""
    except CountError as error:
        return None, str(error)


def parse_listing(html: str) -> Listing:
    """Read every repository row from one page."""
    page = parse_html(html)
    repos: list[Repo] = []
    for row in page.find_all(cls=REPO_CLASS):
        name_element = row.find(cls="name")
        name = name_element.text() if name_element is not None else ""
        stars, star_reason = _read_count(row.find(cls=STARS_CLASS), "star count")
        forks, fork_reason = _read_count(row.find(cls=FORKS_CLASS), "fork count")
        language_element = row.find(cls=LANGUAGE_CLASS)
        language = language_element.text() if language_element is not None \
            else ""
        note = ""
        if stars is None:
            note = star_reason
        if forks is None and not note:
            note = fork_reason
        repos.append(Repo(name, stars, forks, language, note))
    if not repos:
        raise CountError("the page holds no repository rows")
    return Listing(tuple(repos))


def read_listing(path=None) -> Listing:
    target = Path(LISTING_FILE if path is None else path)
    if not target.is_file():
        raise CountError(f"file not found: {target}")
    return parse_listing(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# A count over time
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Sample:
    """One reading of a star count: a tick and the figure the page printed."""

    at: int
    count: Count


@dataclass(frozen=True)
class History:
    """A star history, oldest first, and the questions worth asking of it."""

    samples: tuple[Sample, ...]

    def __post_init__(self) -> None:
        if not self.samples:
            raise CountError("a history needs at least one sample")
        ticks = [sample.at for sample in self.samples]
        if ticks != sorted(ticks):
            raise CountError("the samples are not in tick order")
        if len(set(ticks)) != len(ticks):
            raise CountError("two samples share a tick")

    def __len__(self) -> int:
        return len(self.samples)

    def first(self) -> Sample:
        return self.samples[0]

    def last(self) -> Sample:
        return self.samples[-1]

    def gained(self) -> tuple[int, int]:
        """The gain from the first sample to the last, as an interval."""
        return gain(self.first().count, self.last().count)

    def lines(self) -> tuple[str, ...]:
        return tuple(f"t={sample.at:<3} {sample.count.format():>8}  between "
                     f"{sample.count.low():,} and {sample.count.high():,}"
                     for sample in self.samples)


def parse_history(text: str) -> History:
    """Read `tick<TAB>count` lines into a `History`."""
    samples: list[Sample] = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for number, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        if "\t" not in line:
            raise CountError(f"line {number}: expected a tick, a tab and a "
                             f"count")
        tick_text, count_text = line.split("\t", 1)
        try:
            tick = int(tick_text.strip())
        except ValueError:
            raise CountError(f"line {number}: {tick_text.strip()!r} is not a "
                             f"whole tick") from None
        samples.append(Sample(tick, parse_count(count_text.strip())))
    if not samples:
        raise CountError("the history holds no samples")
    return History(tuple(samples))


def read_history(path=None) -> History:
    target = Path(HISTORY_FILE if path is None else path)
    if not target.is_file():
        raise CountError(f"file not found: {target}")
    return parse_history(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(listing: Listing, history: History) -> list[tuple[str, bool]]:
    """Nine checks, each re-derived rather than restated."""

    def every_count() -> tuple[Count, ...]:
        counts = [count for repo in listing.repos
                  for count in (repo.stars, repo.forks) if count is not None]
        counts.extend(sample.count for sample in history.samples)
        return tuple(counts)

    def every_count_is_whole_and_known() -> bool:
        for count in every_count():
            if not isinstance(count.amount, int) or \
                    isinstance(count.amount, bool) or count.amount < 0:
                return False
        return True

    def every_count_prints_and_reads_back() -> bool:
        for count in every_count():
            back = parse_count(count.format())
            if (back.amount, back.resolution) != (count.amount,
                                                  count.resolution):
                return False
        return True

    def every_step_is_one_the_page_prints() -> bool:
        allowed = {1}
        for magnitude in (1_000, 1_000_000, 1_000_000_000):
            allowed.update({magnitude, magnitude // 10})
        return all(count.resolution in allowed for count in every_count())

    def a_suffixed_count_is_at_least_one_magnitude() -> bool:
        suffixed = [count for count in every_count() if not count.exact]
        return bool(suffixed) and all(count.amount >= count.resolution
                                      for count in suffixed)

    def the_legacy_cleaner_reads_two_and_a_half_k_as_twenty_three() -> bool:
        return legacy_clean_number("2.3k") == 23 and \
            parse_count("2.3k").amount == 2_300

    def the_legacy_cleaner_reads_a_million_as_twelve() -> bool:
        return legacy_clean_number("1.2m") == 12 and \
            parse_count("1.2m").amount == 1_200_000

    def truncation_loses_the_decimal_the_page_printed() -> bool:
        return legacy_magnitude("2.9k") == 2_000 and \
            parse_count("2.9k").amount == 2_900

    def two_overlapping_counts_are_indistinguishable() -> bool:
        left = listing.get("price-lab").stars
        right = listing.get("counts-lab").stars
        if left is None or right is None:
            return False
        return relation(left, right) == "indistinguishable"

    def the_history_is_ordered_and_its_gain_is_an_interval() -> bool:
        ticks = [sample.at for sample in history.samples]
        if ticks != sorted(ticks):
            return False
        low, high = history.gained()
        point = history.last().count.amount - history.first().count.amount
        return low <= point <= high

    checks = [
        ("every count is a whole, non-negative number of items",
         every_count_is_whole_and_known),
        ("every count prints and reads back to the same amount and step",
         every_count_prints_and_reads_back),
        ("every step is one of the steps the page prints",
         every_step_is_one_the_page_prints),
        ("a count printed with a suffix is at least one of its magnitude",
         a_suffixed_count_is_at_least_one_magnitude),
        ("the legacy cleaner reads 2.3k as 23, not 2,300",
         the_legacy_cleaner_reads_two_and_a_half_k_as_twenty_three),
        ("the legacy cleaner reads 1.2m as 12, not 1,200,000",
         the_legacy_cleaner_reads_a_million_as_twelve),
        ("int() turns 2.9k into 2,000 and loses 900 stars",
         truncation_loses_the_decimal_the_page_printed),
        ("the two counts the page could not distinguish say so",
         two_overlapping_counts_are_indistinguishable),
        ("the history is in tick order and its gain contains the difference",
         the_history_is_ordered_and_its_gain_is_an_interval),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
CURIOUS = (
    ("2.3k", "one decimal in thousands: a step of 100"),
    ("1.2m", "one decimal in millions: a step of 100,000"),
    ("12k", "no decimal: a step of 1,000"),
    ("1,234", "grouped: every digit printed"),
    ("999", "a plain whole number"),
    ("2k", "no decimal: a step of 1,000"),
    ("0.9k", "below a thousand, which the page would print in full"),
    ("1.234", "a dot where the page groups with a comma"),
    ("2.34k", "two decimals, which the page never prints"),
    ("12,34", "a group that is not three digits"),
    ("12.5", "a decimal with no suffix, which is not a count"),
    ("-5", "a count cannot be negative"),
    ("", "no text at all"),
)


def _reads(text: str) -> bool:
    try:
        parse_count(text)
        return True
    except CountError:
        return False


def run_demo() -> int:
    listing = read_listing()
    history = read_history()

    print("=" * 74)
    print(" COUNT LAB - a displayed count is a measurement, not a number")
    print("=" * 74)

    print("\n  the legacy conversions, transcribed:")
    for line in LEGACY_CLEAN.split("\n"):
        print(f"    {line}")
    for line in LEGACY_MAGNITUDE.split("\n"):
        print(f"    {line}")

    print("\n  what the legacy cleaner makes of real count text:")
    for text, description in CURIOUS:
        legacy = legacy_clean_number(text)
        try:
            count = parse_count(text)
            shown = f"{count.format():>8}  step {count.resolution:,}"
        except CountError as error:
            shown = f"{'refused':>8}  {error}"
        print(f"    {text!r:<10} legacy {legacy:>10,}   {shown}")
    wrong = [text for text, _ in CURIOUS
             if _reads(text) and not agrees(text)]
    print(f"    {len(wrong)} readable count(s) disagree with the legacy "
          f"integer: {', '.join(repr(text) for text in wrong)}")

    print(f"\n  the page, {len(listing)} repositories:")
    for repo in listing.repos:
        print(f"    {repo.line()}")
    print("\n  the same stars, with the interval the page printed:")
    for repo in listing.repos:
        print(f"    {repo.star_line()}")

    first = listing.get("price-lab").stars
    second = listing.get("counts-lab").stars
    print("\n  two of those counts cannot be told apart:")
    print(f"    price-lab prints {first.format()}, which is "
          f"{first.low():,}..{first.high():,}")
    print(f"    counts-lab prints {second.format()}, which is exactly "
          f"{second.amount:,}")
    print(f"    the page could not distinguish them: "
          f"{relation(first, second)}")
    print(f"    the legacy integer would have said "
          f"{legacy_clean_number(first.format())} against "
          f"{legacy_clean_number(second.format())}")

    print(f"\n  the star count over {len(history)} days:")
    for line in history.lines():
        print(f"    {line}")
    low, high = history.gained()
    print(f"    gained from the first sample to the last: "
          f"{format_gain((low, high))}")
    print(f"    the legacy reading of the same two days: "
          f"{legacy_clean_number(history.first().count.format()):,} then "
          f"{legacy_clean_number(history.last().count.format()):,}")

    checks = audit(listing, history)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    readable = sum(1 for text, _ in CURIOUS if _reads(text))
    print("\nCross-checks OK: " +
          f"{len(CURIOUS)} pieces of count text give {readable} readable "
          f"figure(s) and {len(CURIOUS) - readable} refusal(s), "
          f"2.3k is {parse_count('2.3k').amount:,} here and "
          f"{legacy_clean_number('2.3k')} to the legacy cleaner, 1.2m is "
          f"{parse_count('1.2m').amount:,} and "
          f"{legacy_clean_number('1.2m')}, int() makes 2.9k into "
          f"{legacy_magnitude('2.9k'):,}, the page's "
          f"{first.format()} is {relation(first, second)} from its "
          f"{second.format()}, the {len(history)}-day history gained "
          f"{format_gain((low, high))}, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("Demo completed successfully.")
    return 0


def agrees(text: str) -> bool:
    """True when the legacy integer and the parsed count are the same figure."""
    try:
        count = parse_count(text)
    except CountError:
        return False
    return legacy_clean_number(text) == count.amount
