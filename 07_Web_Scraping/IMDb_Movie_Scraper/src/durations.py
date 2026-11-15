"""A runtime is a quantity in one unit, not the digits in the order they appear.

The legacy scraper read a runtime like this:

    def clean_runtime(value):
        cleaned = re.sub(r"[^\\d]", "", value)
        try:
            return int(cleaned)
        except ValueError:
            return 0

**1. Deleting the units concatenates the fields.** `"2h 15min"` loses the `h` and
the `min`, and `"215"` is what is left -- two hundred and fifteen minutes for a film
that runs a hundred and thirty-five. The units are not decoration; they are the only
thing that says what the digits mean.

**2. Two spellings of the same length became two different numbers.** IMDb prints the
same film as `"2h 15min"` on one page and `"135 min"` on another. The legacy reader
answers 215 and 135, so a comparison says the two rows are seventy minutes apart.

**3. A colon is not a runtime.** `"2:15"` could be two hours fifteen or two minutes
fifteen, and the same three characters mean different things in a duration field and a
clock field. A runtime is read from units, and a colon form is refused with the reason
rather than guessed.

**4. Zero is not "unknown".** Every failure path returns `0`, so a film whose runtime
the page did not print becomes a film that runs for no time at all -- and then a
marathon planner happily schedules it.

**5. A series is a runtime with a count.** Twenty-four episodes of forty-seven minutes
is 1,128 minutes, and the legacy reader can only ever hold one of those two numbers.

So this module keeps a runtime as **whole minutes in one unit**, converts hours and
minutes by arithmetic rather than by concatenation, refuses the shapes that are
ambiguous, keeps an unknown runtime as unknown, and multiplies a per-episode runtime
by its episode count. The marathon planner spends a budget in whole films.

The demonstration is offline: one bundled page, one bundled budget, and no network.

Standard library only: no requests, no beautifulsoup, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TITLES_FILE = DATA_DIR / "titles.html"

#: The legacy conversion, transcribed, so the demo can refute it.
LEGACY_RUNTIME = ('cleaned = re.sub(r"[^\\d]", "", value)\n'
                  'try:\n'
                  '    return int(cleaned)\n'
                  'except ValueError:\n'
                  '    return 0')

#: The minutes in an hour, which is the only conversion this module needs.
MINUTES_PER_HOUR = 60

#: An hours field: `2h`, `2 h`, `2 hours`, `2 hour`, `2h15min`.
HOURS = re.compile(r"(\d+)\s*(?:hours|hour|hrs|hr|h)(?![a-zA-Z])")

#: A minutes field: `15min`, `15 min`, `15 minutes`, `15m`.
MINUTES = re.compile(r"(\d+)\s*(?:minutes|minute|mins|min|m)(?![a-zA-Z])")

#: Seconds, which a runtime is never printed in.
SECONDS = re.compile(r"(\d+)\s*(?:seconds|second|secs|sec|s)(?![a-zA-Z])")

#: A bare whole number, which this module reads as minutes.
BARE = re.compile(r"^\d+$")

#: The separators a two-field runtime may use between its fields.
JOINERS = re.compile(r"^[\s,]*$")

#: The budget the bundled marathon plans against, in minutes.
BUDGET_MINUTES = 300


class DurationError(Exception):
    """A runtime that cannot be read, with the sentence that says why."""


# --------------------------------------------------------------------------- #
# A duration
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, order=True)
class Duration:
    """A runtime, as whole minutes in one unit.

    One unit, because two numbers in two units is exactly how `2h 15min` became
    215: the fields were stored apart and printed together.
    """

    minutes: int

    def __post_init__(self) -> None:
        if not isinstance(self.minutes, int) or isinstance(self.minutes, bool):
            raise DurationError(f"a runtime is a whole number of minutes, got "
                                f"{self.minutes!r}")
        if self.minutes < 0:
            raise DurationError(f"a runtime cannot be negative, got "
                                f"{self.minutes}")

    @property
    def hours(self) -> int:
        return self.minutes // MINUTES_PER_HOUR

    @property
    def rest(self) -> int:
        """The minutes left after the whole hours."""
        return self.minutes % MINUTES_PER_HOUR

    def plus(self, other: "Duration") -> "Duration":
        return Duration(self.minutes + other.minutes)

    def times(self, count: int) -> "Duration":
        if not isinstance(count, int) or isinstance(count, bool):
            raise DurationError(f"a count is a whole number, got {count!r}")
        if count < 0:
            raise DurationError(f"a count cannot be negative, got {count}")
        return Duration(self.minutes * count)

    def format(self) -> str:
        """`2h 15min` when there is an hour, `45min` when there is not."""
        if self.minutes == 0:
            return "0min"
        if self.hours == 0:
            return f"{self.rest}min"
        if self.rest == 0:
            return f"{self.hours}h"
        return f"{self.hours}h {self.rest}min"

    def __str__(self) -> str:
        return self.format()


def parse_duration(text: str) -> Duration:
    """Read a runtime from the text a title page prints.

    The rules, each a refusal rather than a guess:

    * hours and minutes are separate fields, added, never concatenated;
    * a minutes field is below 60 -- `2h 75min` is written `3h 15min`;
    * a bare number is minutes, because that is what the page prints;
    * a colon form is refused: `2:15` does not say which unit is which;
    * seconds are refused: a runtime is printed in minutes;
    * anything left over after the fields is refused, by name.
    """
    if not isinstance(text, str):
        raise DurationError(f"a runtime is text, got {type(text).__name__}")
    body = text.strip()
    if not body:
        raise DurationError("the runtime text is empty")
    if ":" in body:
        raise DurationError(f"{body!r} is a clock form, not a runtime: '2:15' "
                            f"could be two hours fifteen or two minutes "
                            f"fifteen, and the page prints units")

    if BARE.match(body):
        return Duration(int(body))

    if SECONDS.search(body):
        raise DurationError(f"{body!r} names seconds, and a runtime is printed "
                            f"in hours and minutes")

    hours = HOURS.findall(body)
    minutes = MINUTES.findall(body)
    if len(hours) > 1 or len(minutes) > 1:
        raise DurationError(f"{body!r} names the same unit twice")
    if not hours and not minutes:
        raise DurationError(f"no hours and no minutes in {body!r}")

    leftover = body
    if hours:
        leftover = HOURS.sub(" ", leftover, count=1)
    if minutes:
        leftover = MINUTES.sub(" ", leftover, count=1)
    if not JOINERS.match(leftover.replace("and", " ")):
        raise DurationError(f"a runtime cannot hold "
                            f"{leftover.strip()!r}, but {body!r} does")

    if hours and minutes and int(minutes[0]) >= MINUTES_PER_HOUR:
        raise DurationError(f"{body!r} states {minutes[0]} minutes beside an "
                            f"hour, and a minute field is below 60: write it "
                            f"as hours")

    total = 0
    if hours:
        total += int(hours[0]) * MINUTES_PER_HOUR
    if minutes:
        total += int(minutes[0])
    return Duration(total)


# --------------------------------------------------------------------------- #
# The legacy conversion, executable
# --------------------------------------------------------------------------- #
def legacy_minutes(value: str | None) -> int:
    """The legacy reader, rewritten faithfully: digits concatenated, or `0`."""
    if not value:
        return 0
    cleaned = re.sub(r"[^\d]", "", value)
    try:
        return int(cleaned)
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
        raise DurationError(f"a page is text, got {type(text).__name__}")
    builder = _Builder()
    builder.feed(text)
    builder.close()
    return builder.root


# --------------------------------------------------------------------------- #
# Titles
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Film:
    """One row: a title, the runtime it printed, and a year."""

    title: str
    runtime: Duration | None
    year: str
    note: str

    def line(self) -> str:
        shown = self.runtime.format() if self.runtime else "?"
        return f"{self.title:<12} {shown:>10}  {self.year}"

    def minutes_line(self) -> str:
        """The runtime in the one unit, with the reason when there is none."""
        if self.runtime is None:
            return f"{self.title:<12} {'?':>10}  ({self.note})"
        return f"{self.title:<12} {self.runtime.minutes:>7} min"


@dataclass(frozen=True)
class Series:
    """A title with a runtime per episode and a count of episodes."""

    title: str
    per_episode: Duration | None
    episodes: int
    note: str

    def total(self) -> Duration | None:
        """Every episode, as one runtime -- unknown if either half is."""
        if self.per_episode is None or self.episodes <= 0:
            return None
        return self.per_episode.times(self.episodes)

    def line(self) -> str:
        each = self.per_episode.format() if self.per_episode else "?"
        total = self.total()
        shown = total.format() if total else "?"
        return f"{self.title:<12} {each:>6} x {self.episodes:<3} = {shown:>9}"


@dataclass(frozen=True)
class Catalogue:
    """Every row on the page, films and series, in page order."""

    films: tuple[Film, ...]
    series: tuple[Series, ...]

    def __post_init__(self) -> None:
        if not self.films and not self.series:
            raise DurationError("a catalogue needs at least one title")
        titles = [film.title for film in self.films] + \
            [series.title for series in self.series]
        if len(set(titles)) != len(titles):
            raise DurationError("two titles share a name")

    def film(self, title: str) -> Film:
        for film in self.films:
            if film.title == title:
                return film
        raise DurationError(f"no film titled {title!r} on the page")

    def known_runtimes(self) -> tuple[Duration, ...]:
        return tuple(film.runtime for film in self.films
                     if film.runtime is not None)

    def unknown(self) -> tuple[Film, ...]:
        return tuple(film for film in self.films if film.runtime is None)


def _read_runtime(element: Element | None) -> tuple[Duration | None, str]:
    if element is None:
        return None, "the page prints no runtime"
    text = element.text()
    if not text:
        return None, "the runtime is empty"
    try:
        return parse_duration(text), ""
    except DurationError as error:
        return None, str(error)


def parse_catalogue(html: str) -> Catalogue:
    """Read every row on the page, keeping films and series apart."""
    page = parse_html(html)
    films: list[Film] = []
    series: list[Series] = []
    for row in page.find_all(cls="row"):
        title_element = row.find(cls="title")
        title = title_element.text() if title_element is not None else ""
        runtime, reason = _read_runtime(row.find(cls="runtime"))
        year_element = row.find(cls="year")
        year = year_element.text() if year_element is not None else ""
        if "series" in row.classes():
            episodes_element = row.find(cls="episodes")
            episodes_text = episodes_element.text() if episodes_element \
                is not None else ""
            try:
                episodes = int(episodes_text)
            except ValueError:
                episodes = 0
            note = reason or ("" if episodes > 0 else
                              "the page prints no episode count")
            series.append(Series(title, runtime, episodes, note))
        else:
            films.append(Film(title, runtime, year, reason))
    if not films and not series:
        raise DurationError("the page holds no titles")
    return Catalogue(tuple(films), tuple(series))


def read_catalogue(path=None) -> Catalogue:
    target = Path(TITLES_FILE if path is None else path)
    if not target.is_file():
        raise DurationError(f"file not found: {target}")
    return parse_catalogue(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# A marathon
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Marathon:
    """A budget in minutes and the films that fit inside it, in page order."""

    budget: Duration
    films: tuple[Film, ...]

    def total(self) -> Duration | None:
        """The planned runtime, or unknown if a planned film has no runtime."""
        total = Duration(0)
        for film in self.films:
            if film.runtime is None:
                return None
            total = total.plus(film.runtime)
        return total

    def remaining(self) -> Duration | None:
        """What is left of the budget, or None when the plan does not fit.

        `None` rather than a negative runtime, because a duration cannot be
        negative and "minus fifteen minutes left" is not a thing a budget has.
        """
        total = self.total()
        if total is None or total.minutes > self.budget.minutes:
            return None
        return Duration(self.budget.minutes - total.minutes)

    def fits(self) -> bool:
        total = self.total()
        return total is not None and total.minutes <= self.budget.minutes

    def titles(self) -> tuple[str, ...]:
        return tuple(film.title for film in self.films)

    def line(self) -> str:
        total = self.total()
        shown = total.format() if total else "?"
        left = self.remaining()
        if left is None:
            rest = "over budget"
        else:
            rest = f"{left.format()} left"
        return (f"{len(self.films)} film(s) of {self.budget.format()}: "
                f"{shown} used, {rest}")


def plan(films: tuple[Film, ...], budget: Duration) -> Marathon:
    """Take films in the order given, while each one still fits.

    A film with no runtime is skipped, not guessed at: there is no way to know
    whether it fits, and a planner that assumes zero schedules a film nobody can
    finish.
    """
    chosen: list[Film] = []
    spent = 0
    for film in films:
        if film.runtime is None:
            continue
        if spent + film.runtime.minutes <= budget.minutes:
            chosen.append(film)
            spent += film.runtime.minutes
    return Marathon(budget, tuple(chosen))


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(catalogue: Catalogue, series: Series, marathon: Marathon) -> \
        list[tuple[str, bool]]:
    """Nine checks, each re-derived rather than restated."""

    def every_runtime_is_whole_minutes() -> bool:
        return all(isinstance(runtime.minutes, int) and
                   not isinstance(runtime.minutes, bool) and
                   runtime.minutes >= 0
                   for runtime in catalogue.known_runtimes())

    def every_runtime_prints_and_reads_back() -> bool:
        for runtime in catalogue.known_runtimes():
            if parse_duration(runtime.format()) != runtime:
                return False
        return True

    def the_two_spellings_of_the_same_length_agree() -> bool:
        first = catalogue.film("Long One").runtime
        second = catalogue.film("Long Two").runtime
        return first is not None and first == second and \
            first.minutes == 135

    def the_legacy_reader_concatenates_hours_and_minutes() -> bool:
        return legacy_minutes("2h 15min") == 215 and \
            parse_duration("2h 15min").minutes == 135

    def the_legacy_reader_concatenates_an_hour_and_forty_seven() -> bool:
        return legacy_minutes("1h 47min") == 147 and \
            parse_duration("1h 47min").minutes == 107

    def an_unknown_runtime_is_unknown_and_not_zero() -> bool:
        return len(catalogue.unknown()) == 1 and \
            all(runtime.minutes > 0 for runtime in catalogue.known_runtimes())

    def a_series_total_is_the_product_of_its_two_fields() -> bool:
        total = series.total()
        if total is None:
            return False
        return total.minutes == series.per_episode.minutes * series.episodes \
            and total.minutes >= series.per_episode.minutes

    def the_marathon_never_spends_more_than_its_budget() -> bool:
        return marathon.fits() and marathon.remaining() is not None

    def the_marathon_never_plans_a_film_twice() -> bool:
        titles = marathon.titles()
        return len(set(titles)) == len(titles) and \
            all(film.runtime is not None for film in marathon.films)

    checks = [
        ("every runtime is a whole number of minutes",
         every_runtime_is_whole_minutes),
        ("every runtime prints and reads back to the same minutes",
         every_runtime_prints_and_reads_back),
        ("the two spellings of 135 minutes are the same runtime",
         the_two_spellings_of_the_same_length_agree),
        ("the legacy reader makes 2h 15min into 215 minutes",
         the_legacy_reader_concatenates_hours_and_minutes),
        ("the legacy reader makes 1h 47min into 147 minutes",
         the_legacy_reader_concatenates_an_hour_and_forty_seven),
        ("the film whose runtime is missing is unknown, and no runtime is zero",
         an_unknown_runtime_is_unknown_and_not_zero),
        ("a series total is its episode count times its per-episode runtime",
         a_series_total_is_the_product_of_its_two_fields),
        ("the marathon never spends more than its budget",
         the_marathon_never_spends_more_than_its_budget),
        ("the marathon never plans a film twice or without a runtime",
         the_marathon_never_plans_a_film_twice),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
CURIOUS = (
    ("135 min", "minutes, spelled out"),
    ("135", "a bare number, which the page prints as minutes"),
    ("2h 15min", "hours and minutes, the shape the page also prints"),
    ("2h", "hours alone"),
    ("2 hours 15 minutes", "the same runtime, written long"),
    ("1h 47min", "an hour and forty-seven"),
    ("45min", "less than an hour"),
    ("2h 75min", "a minute field of 75, which is written 3h 15min"),
    ("2:15", "a colon, which does not say which unit is which"),
    ("2h 15min 30s", "seconds, which a runtime never prints"),
    ("", "no text at all"),
)


def _reads(text: str) -> bool:
    try:
        parse_duration(text)
        return True
    except DurationError:
        return False


def run_demo() -> int:
    catalogue = read_catalogue()
    show = catalogue.series[0]
    marathon = plan(catalogue.films, Duration(BUDGET_MINUTES))

    print("=" * 74)
    print(" RUNTIME LAB - a runtime is a quantity in one unit, not concatenated digits")
    print("=" * 74)

    print("\n  the legacy conversion, transcribed:")
    for line in LEGACY_RUNTIME.split("\n"):
        print(f"    {line}")

    print("\n  what the legacy reader makes of real runtime text:")
    for text, description in CURIOUS:
        legacy = legacy_minutes(text)
        try:
            runtime = parse_duration(text)
            shown = f"{runtime.format():>10}  {runtime.minutes:>5} min"
        except DurationError as error:
            shown = f"{'refused':>10}  {error}"
        print(f"    {text!r:<22} legacy {legacy:>6}   {shown}")
    wrong = [text for text, _ in CURIOUS if _reads(text) and not agrees(text)]
    print(f"    {len(wrong)} readable runtime(s) disagree with the legacy "
          f"integer: {', '.join(repr(text) for text in wrong)}")

    print(f"\n  the page, {len(catalogue.films)} films:")
    for film in catalogue.films:
        print(f"    {film.line()}")
    print("\n  the same runtimes in the one unit:")
    for film in catalogue.films:
        print(f"    {film.minutes_line()}")

    first = catalogue.film("Long One").runtime
    second = catalogue.film("Long Two").runtime
    print("\n  one length, two spellings:")
    print(f"    Long One prints '2h 15min' -> {first.minutes} minutes")
    print(f"    Long Two prints '135 min'  -> {second.minutes} minutes")
    print(f"    the same runtime: {first == second}")
    print(f"    the legacy reader says "
          f"{legacy_minutes('2h 15min')} and {legacy_minutes('135 min')}, so "
          f"it thinks they differ by "
          f"{legacy_minutes('2h 15min') - legacy_minutes('135 min')} minutes")

    print(f"\n  the series:")
    print(f"    {show.line()}")
    print(f"    {show.episodes} episodes of "
          f"{show.per_episode.minutes} minutes is "
          f"{show.total().minutes:,} minutes")
    print(f"    the legacy reader can only hold one of those two numbers: "
          f"{legacy_minutes(f'{show.episodes} episodes')} or "
          f"{legacy_minutes(show.per_episode.format())}")

    print(f"\n  a marathon with {marathon.budget.format()} to spend:")
    print(f"    {marathon.line()}")
    for film in marathon.films:
        print(f"    takes {film.title:<12} {film.runtime.format():>10}")
    skipped = [film.title for film in catalogue.films
               if film.title not in marathon.titles()]
    print(f"    leaves {', '.join(skipped)}")
    print(f"    every planned film fits: {marathon.fits()}")

    checks = audit(catalogue, show, marathon)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    readable = sum(1 for text, _ in CURIOUS if _reads(text))
    print("\nCross-checks OK: " +
          f"{len(CURIOUS)} pieces of runtime text give {readable} readable "
          f"runtime(s) and {len(CURIOUS) - readable} refusal(s), "
          f"2h 15min is {parse_duration('2h 15min').minutes} minutes here and "
          f"{legacy_minutes('2h 15min')} to the legacy reader, 135 min is "
          f"{parse_duration('135 min').minutes}, the two spellings are "
          f"{'the same' if first == second else 'different'}, the "
          f"{show.episodes}-episode series is {show.total().minutes:,} minutes "
          f"({show.total().format()}), the marathon spends "
          f"{marathon.total().minutes} of {marathon.budget.minutes} minutes, "
          f"and {sum(1 for _, okay in checks if okay)}/{len(checks)} checks "
          f"hold")

    print("\nDemo completed successfully.")
    return 0


def agrees(text: str) -> bool:
    """True when the legacy integer and the parsed minutes are the same."""
    try:
        runtime = parse_duration(text)
    except DurationError:
        return False
    return legacy_minutes(text) == runtime.minutes
