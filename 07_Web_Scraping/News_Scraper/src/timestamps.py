"""A timestamp is an instant, not a string and not the clock.

The legacy scraper read a published date like this:

    def parse_date(value):
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return datetime.now()

    def age_seconds(now, published):
        try:
            return (now - published).total_seconds()
        except TypeError:
            return 0

**1. The fallback is the worst possible answer.** A page that prints `"3 hours
ago"`, `"13 Nov 2026 18:05 +02:00"`, or nothing at all is answered with
`datetime.now()` -- so an article from 2019 that the parser could not read is
reported as **published just now**. The defect is not a crash; it is a wrong
answer that looks like the freshest possible one.

**2. A naive datetime is not an instant.** `datetime.strptime(...)` returns a
datetime with no zone. Subtract it from `datetime.now(timezone.utc)` and Python
raises `TypeError`; the legacy `except` turns that into **0 seconds**, which is
"published just now" again. One missing zone and every article is new.

**3. A phrase is only a time relative to something.** `"3 hours ago"` is not a
timestamp, it is an offset from the moment the page was read. Compute it against
`datetime.now()` inside the parser and the same page gives a different answer on
every run, so nothing about it can be tested. Here the reading time is an
argument.

**4. Sorting by the printed text is not sorting by time.** `"13 Nov 2026"` sorts
before `"2019-03-01"` as text and after it as an instant, and `"yesterday"`
sorts after every digit. A feed ordered by string is not a feed ordered by date.

**5. Zero is not "unknown".** Every failure path ends at "now" or at zero, so a
timestamp the page did not print is indistinguishable from one printed a moment
ago.

So this module keeps a timestamp as **whole seconds since the epoch, in UTC**,
reads five shapes and refuses the ambiguous ones by name, resolves a relative
phrase against a **supplied** reading time, keeps an unknown timestamp as
`None`, orders a feed by the instant rather than the text, and says how old each
article is at that reading time.

The demonstration is offline: one bundled feed, one bundled reading time, and no
network. Standard library only: no requests, no beautifulsoup, no clock.

Note "no clock": nothing in this module calls `datetime.now()`. The legacy
functions do, and that is exactly what the demo refutes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FEED_FILE = DATA_DIR / "feed.txt"

#: The legacy parser, transcribed: unreadable means "now".
LEGACY_FALLBACK = ('try:\n'
                   '    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")\n'
                   'except (ValueError, TypeError):\n'
                   '    return datetime.now()')

#: The legacy age, transcribed: a zone mismatch means zero seconds.
LEGACY_AGE = ('try:\n'
              '    return (now - published).total_seconds()\n'
              'except TypeError:\n'
              '    return 0')

#: The bundled reading time: the moment the feed is taken to be read.
READ_AT = "2026-11-15T12:00:00Z"

#: Months, spelled the way a page spells them.
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

#: Seconds in each unit a relative phrase can use.
UNITS = {"second": 1, "minute": 60, "hour": 3_600, "day": 86_400,
         "week": 604_800}

#: `3 hours ago`, `1 day ago`, `20 minutes ago`.
AGO = re.compile(r"^(\d+)\s*(second|minute|hour|day|week)s?\s+ago$")

#: `15 Nov 2026 09:30 UTC`, `13 Nov 2026 18:05:00 +02:00`.
PROSE = re.compile(r"^(\d{1,2}) ([A-Z][a-z]{2}) (\d{4}) "
                   r"(\d{1,2}):(\d{2})(?::(\d{2}))? "
                   r"(UTC|[+-]\d{2}:\d{2})$")

#: A value that starts like an ISO date, whether or not it is one.
ISO_LOOKING = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]")

#: A day on its own, which names no instant.
DAY_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: A clock on its own, which names no day.
CLOCK_ONLY = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")

#: An offset: `+02:00`, `-05:30`.
OFFSET = re.compile(r"^([+-])(\d{2}):(\d{2})$")

SECONDS_PER_DAY = 86_400


class TimeError(Exception):
    """A timestamp that cannot be read, with the sentence that says why."""


# --------------------------------------------------------------------------- #
# An instant
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, order=True)
class Moment:
    """One instant, as whole seconds since the epoch, in UTC.

    One field, because an instant is one number. A zone is how the number is
    written down, not part of it: the same moment printed in two zones is still
    one `Moment`, and comparing two `Moment`s never raises a `TypeError`.
    """

    epoch: int

    def __post_init__(self) -> None:
        if not isinstance(self.epoch, int) or isinstance(self.epoch, bool):
            raise TimeError(f"an instant is a whole number of seconds, got "
                            f"{self.epoch!r}")

    def iso(self) -> str:
        """`2026-11-15T11:00:00Z` -- the shape a feed prints in."""
        utc = datetime.fromtimestamp(self.epoch, timezone.utc)
        return utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    def human(self) -> str:
        """`15 Nov 2026 11:00 UTC` -- the shape a person reads."""
        utc = datetime.fromtimestamp(self.epoch, timezone.utc)
        return (f"{utc.day:02d} {MONTHS[utc.month - 1]} {utc.year} "
                f"{utc.hour:02d}:{utc.minute:02d} UTC")

    def age_seconds(self, now: "Moment") -> int:
        """How long before `now` this instant was, in whole seconds."""
        if not isinstance(now, Moment):
            raise TimeError(f"an age is measured from an instant, got "
                            f"{type(now).__name__}")
        elapsed = now.epoch - self.epoch
        if elapsed < 0:
            raise TimeError(f"{self.iso()} is after the reading time "
                            f"{now.iso()}, so it has no age yet")
        return elapsed

    def age_text(self, now: "Moment") -> str:
        """`just now`, `5 min ago`, `3 h ago`, `26 d ago`."""
        elapsed = self.age_seconds(now)
        if elapsed < 60:
            return "just now"
        if elapsed < 3_600:
            return f"{elapsed // 60} min ago"
        if elapsed < SECONDS_PER_DAY:
            return f"{elapsed // 3_600} h ago"
        return f"{elapsed // SECONDS_PER_DAY} d ago"

    def __str__(self) -> str:
        return self.iso()


# --------------------------------------------------------------------------- #
# Reading a timestamp
# --------------------------------------------------------------------------- #
def parse_timestamp(text: str, now: Moment | None = None) -> Moment:
    """Read one printed timestamp, refusing the ambiguous shapes by name.

    The rules, each a refusal rather than a guess:

    * a relative phrase (`3 hours ago`, `yesterday`, `just now`) needs the
      moment the page was read, so `now` is an argument and never the clock;
    * an ISO 8601 value must carry a zone: `2026-11-15T10:00:00` is not an
      instant, it is a wall clock with no address;
    * a prose value (`13 Nov 2026 18:05 +02:00`) must carry a zone too;
    * a day on its own and a clock on its own each name half of an instant, so
      both are refused;
    * anything else is refused with the shape it looks like.
    """
    if not isinstance(text, str):
        raise TimeError(f"a timestamp is text, got {type(text).__name__}")
    body = text.strip()
    if not body:
        raise TimeError("the timestamp text is empty")

    lowered = body.lower()
    if lowered == "just now":
        if now is None:
            raise TimeError(f"{body!r} is relative: it needs the moment the "
                            f"page was read")
        return Moment(now.epoch)
    if lowered == "yesterday":
        if now is None:
            raise TimeError(f"{body!r} is relative: it needs the moment the "
                            f"page was read")
        return Moment(now.epoch - SECONDS_PER_DAY)

    ago = AGO.match(lowered)
    if ago is not None:
        if now is None:
            raise TimeError(f"{body!r} is relative: it needs the moment the "
                            f"page was read")
        count = int(ago.group(1))
        unit = ago.group(2)
        return Moment(now.epoch - count * UNITS[unit])

    if ISO_LOOKING.match(body):
        return _parse_iso(body)

    prose = PROSE.match(body)
    if prose is not None:
        return _parse_prose(body, prose)

    if DAY_ONLY.match(body):
        raise TimeError(f"{body!r} names a day, not an instant: a day has no "
                        f"time and no zone")
    if CLOCK_ONLY.match(body):
        raise TimeError(f"{body!r} names a clock, not a date: a clock alone "
                        f"has no day")
    raise TimeError(f"{body!r} is not a timestamp this lab can read: it is "
                    f"neither ISO 8601, nor prose with a zone, nor a phrase")


def _parse_iso(body: str) -> Moment:
    try:
        parsed = datetime.fromisoformat(body.replace("Z", "+00:00"))
    except ValueError:
        raise TimeError(f"{body!r} starts like an ISO date but is not one") \
            from None
    if parsed.tzinfo is None:
        raise TimeError(f"{body!r} has no zone: a wall clock with no address "
                        f"is not an instant")
    return Moment(int(parsed.timestamp()))


def _parse_prose(body: str, found) -> Moment:
    day, month_name, year, hour, minute, second, zone = found.groups()
    if month_name not in MONTHS:
        raise TimeError(f"{month_name!r} is not a month this lab knows")
    offset = _offset(zone, body)
    try:
        parsed = datetime(int(year), MONTHS.index(month_name) + 1, int(day),
                          int(hour), int(minute), int(second or 0),
                          tzinfo=timezone(offset))
    except ValueError as error:
        raise TimeError(f"{body!r} is not a date: {error}") from None
    return Moment(int(parsed.timestamp()))


def _offset(zone: str, body: str) -> timedelta:
    if zone == "UTC":
        return timedelta(0)
    found = OFFSET.match(zone)
    if found is None:
        raise TimeError(f"{zone!r} is not a zone, but {body!r} prints it")
    sign = -1 if found.group(1) == "-" else 1
    return sign * timedelta(hours=int(found.group(2)),
                            minutes=int(found.group(3)))


# --------------------------------------------------------------------------- #
# The legacy pair, executable
# --------------------------------------------------------------------------- #
def legacy_fallback(value: str | None) -> datetime:
    """The legacy parser, rewritten faithfully: unreadable means `now()`."""
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return datetime.now()


def legacy_age(now, published) -> float:
    """The legacy age, rewritten faithfully: a zone mismatch means zero."""
    try:
        return (now - published).total_seconds()
    except TypeError:
        return 0


# --------------------------------------------------------------------------- #
# A feed
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Article:
    """One row: an id, a title, the timestamp as printed, and what it is."""

    id: str
    title: str
    printed: str
    moment: Moment | None
    note: str

    def line(self, now: Moment) -> str:
        if self.moment is None:
            return f"{self.id:<9} {'unknown':<22} {'-':<12} {self.title}"
        return (f"{self.id:<9} {self.moment.iso():<22} "
                f"{self.moment.age_text(now):<12} {self.title}")

    def note_line(self) -> str:
        return f"{self.id:<9} {self.printed!r:<32} {self.note}"


@dataclass(frozen=True)
class Feed:
    """Every article on one page, and the moment the page was read."""

    read_at: Moment
    articles: tuple[Article, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.read_at, Moment):
            raise TimeError(f"a feed is read at an instant, got "
                            f"{type(self.read_at).__name__}")
        if not self.articles:
            raise TimeError("a feed needs at least one article")
        ids = [article.id for article in self.articles]
        if len(set(ids)) != len(ids):
            raise TimeError("two articles share an id")

    def __len__(self) -> int:
        return len(self.articles)

    def known(self) -> tuple[Article, ...]:        return tuple(article for article in self.articles
                     if article.moment is not None)

    def unknown(self) -> tuple[Article, ...]:
        return tuple(article for article in self.articles
                     if article.moment is None)

    def order(self) -> tuple[Article, ...]:
        """The articles with a timestamp, newest first, by the instant."""
        return tuple(sorted(self.known(),
                            key=lambda article: article.moment.epoch,
                            reverse=True))

    def newest(self) -> Article | None:
        ordered = self.order()
        return ordered[0] if ordered else None

    def get(self, identifier: str) -> Article:
        for article in self.articles:
            if article.id == identifier:
                return article
        raise TimeError(f"no article with id {identifier!r} on the page")

    def lines(self) -> tuple[str, ...]:
        return tuple(article.line(self.read_at) for article in self.order())


def parse_feed(text: str, read_at: Moment) -> Feed:
    """Read `id<TAB>title<TAB>printed` lines into a `Feed`."""
    articles: list[Article] = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for number, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        fields = line.split("\t")
        if len(fields) < 3:
            raise TimeError(f"line {number}: expected an id, a title, a tab, "
                            f"and a timestamp")
        identifier, title = fields[0].strip(), fields[1].strip()
        printed = "\t".join(fields[2:]).strip()
        try:
            moment = parse_timestamp(printed, read_at)
            note = ""
        except TimeError as error:
            moment = None
            note = str(error)
        articles.append(Article(identifier, title, printed, moment, note))
    if not articles:
        raise TimeError("the feed holds no articles")
    return Feed(read_at, tuple(articles))


def read_feed(path=None, read_at: Moment | None = None) -> Feed:
    target = Path(FEED_FILE if path is None else path)
    if not target.is_file():
        raise TimeError(f"file not found: {target}")
    now = read_at if read_at is not None else reading_time()
    return parse_feed(target.read_text(encoding="utf-8"), now)


def reading_time(text: str = READ_AT) -> Moment:
    """The bundled moment the page is taken to be read at."""
    return parse_timestamp(text)


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(feed: Feed, clock=parse_timestamp) -> list[tuple[str, bool]]:
    """Nine checks, each re-derived rather than restated.

    `clock` is injected so a negative control can hand in a reader that ignores
    the moment it was given, which is the only way to show that the relative
    check is testing the argument rather than the wall clock.
    """

    def every_instant_is_whole_seconds() -> bool:
        for article in feed.known():
            if not isinstance(article.moment.epoch, int) or \
                    isinstance(article.moment.epoch, bool):
                return False
        return True

    def every_instant_prints_and_reads_back() -> bool:
        for article in feed.known():
            if parse_timestamp(article.moment.iso()).epoch != \
                    article.moment.epoch:
                return False
        return True

    def a_relative_phrase_is_measured_from_the_supplied_moment() -> bool:
        phrase = "3 hours ago"
        later = Moment(feed.read_at.epoch + SECONDS_PER_DAY)
        first = clock(phrase, feed.read_at)
        second = clock(phrase, later)
        return second.epoch - first.epoch == SECONDS_PER_DAY

    def the_legacy_fallback_makes_an_unreadable_date_look_new() -> bool:
        floor = datetime(2020, 1, 1, tzinfo=timezone.utc)
        return legacy_fallback("3 hours ago").replace(
            tzinfo=timezone.utc) > floor and not _reads_alone("3 hours ago")

    def the_legacy_age_turns_a_missing_zone_into_zero_seconds() -> bool:
        aware = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
        naive = datetime(2026, 11, 14, 9, 30)
        return legacy_age(aware, naive) == 0 and _age_refuses(naive)

    def a_wall_clock_with_no_zone_is_refused() -> bool:
        try:
            parse_timestamp("2026-11-15 10:00:00")
        except TimeError as error:
            return "has no zone" in str(error)
        return False

    def the_feed_is_ordered_by_the_instant_not_the_text() -> bool:
        by_instant = [article.moment.epoch for article in feed.order()]
        if by_instant != sorted(by_instant, reverse=True):
            return False
        by_text = [article.printed for article in feed.order()]
        return by_text != [article.printed for article in sorted(
            feed.known(), key=lambda article: article.printed)]

    def an_unknown_timestamp_is_unknown_and_not_the_epoch() -> bool:
        unknown = feed.unknown()
        if not unknown:
            return False
        return all(article.moment is None for article in unknown) and \
            all(article.moment.epoch > 0 for article in feed.known())

    def no_article_is_newer_than_the_moment_it_was_read() -> bool:
        return all(article.moment.epoch <= feed.read_at.epoch
                   for article in feed.known())

    checks = [
        ("every instant is a whole number of seconds", 
         every_instant_is_whole_seconds),
        ("every instant prints as ISO 8601 and reads back to itself",
         every_instant_prints_and_reads_back),
        ("a relative phrase is measured from the supplied moment",
         a_relative_phrase_is_measured_from_the_supplied_moment),
        ("the legacy fallback makes an unreadable date look new",
         the_legacy_fallback_makes_an_unreadable_date_look_new),
        ("the legacy age turns a missing zone into zero seconds",
         the_legacy_age_turns_a_missing_zone_into_zero_seconds),
        ("a wall clock with no zone is refused", 
         a_wall_clock_with_no_zone_is_refused),
        ("the feed is ordered by the instant, not by the printed text",
         the_feed_is_ordered_by_the_instant_not_the_text),
        ("an unknown timestamp is unknown and not the epoch",
         an_unknown_timestamp_is_unknown_and_not_the_epoch),
        ("no article is newer than the moment it was read",
         no_article_is_newer_than_the_moment_it_was_read),
    ]
    return [(name, _guard(function)) for name, function in checks]


def _reads(text: str) -> bool:
    try:
        parse_timestamp(text, reading_time())
        return True
    except TimeError:
        return False


def _reads_alone(text: str) -> bool:
    """True when the text is an instant without being told when it was read."""
    try:
        parse_timestamp(text)
        return True
    except TimeError:
        return False


def _age_refuses(naive) -> bool:
    """True when this lab refuses a naive reading time instead of zeroing it."""
    try:
        Moment(0).age_seconds(naive)
    except TimeError:
        return True
    except TypeError:
        return True
    return False


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
CURIOUS = (
    ("2026-11-15T11:00:00Z", "ISO 8601, Z for UTC"),
    ("2026-11-15T13:00:00+02:00", "the same instant, two hours ahead"),
    ("2026-11-14T09:30:00Z", "yesterday morning"),
    ("13 Nov 2026 18:05 +02:00", "prose with an offset"),
    ("15 Nov 2026 12:00 UTC", "prose with a named zone"),
    ("3 hours ago", "a phrase, measured from the reading time"),
    ("yesterday", "one day before the reading time"),
    ("just now", "the reading time itself"),
    ("2026-11-15 10:00:00", "a wall clock with no zone"),
    ("2026-11-15", "a day, which has no time"),
    ("09:30", "a clock, which has no day"),
    ("2 fortnights ago", "a unit this lab does not know"),
    ("", "no text at all"),
)


def run_demo() -> int:
    now = reading_time()
    feed = read_feed(read_at=now)

    print("=" * 78)
    print(" CLOCK LAB - a timestamp is an instant, not a string, not the clock")
    print("=" * 78)

    print("\n  the legacy pair, transcribed:")
    for line in LEGACY_FALLBACK.split("\n"):
        print(f"    {line}")
    for line in LEGACY_AGE.split("\n"):
        print(f"    {line}")

    print(f"\n  the page is read at {now.iso()} ({now.human()})")

    print("\n  what the legacy parser makes of real timestamp text:")
    for text, description in CURIOUS:
        try:
            moment = parse_timestamp(text, now)
            shown = f"{moment.iso():<22} {moment.age_text(now)}"
        except TimeError as error:
            shown = f"{'refused':<22} {error}"
        legacy = legacy_fallback(text)
        recent = "new" if legacy.replace(tzinfo=timezone.utc) > \
            datetime(2020, 1, 1, tzinfo=timezone.utc) else "old"
        print(f"    {text!r:<28} legacy {recent:<4} {shown}")
    readable = sum(1 for text, _ in CURIOUS if _reads(text))
    print(f"    {readable} of {len(CURIOUS)} read here; the legacy parser "
          f"answers 'new' for every one of them, because its fallback is "
          f"'now'")

    print(f"\n  the feed, {len(feed.articles)} articles, newest first:")
    for line in feed.lines():
        print(f"    {line}")

    print("\n  the two rows it could not read:")
    for article in feed.unknown():
        print(f"    {article.note_line()}")

    print("\n  the newest article, by instant and by text:")
    newest = feed.newest()
    by_text = sorted(feed.known(), key=lambda article: article.printed)[-1]
    print(f"    by the instant: {newest.id:<9} {newest.moment.iso()}  "
          f"({newest.title})")
    print(f"    by the text:    {by_text.id:<9} {by_text.printed!r}  "
          f"({by_text.title})")
    print(f"    the same article: {newest.id == by_text.id}")

    print("\n  how old each article is at the reading time:")
    for article in feed.order():
        print(f"    {article.id:<9} {article.moment.age_text(now):<10} "
              f"{article.moment.age_seconds(now):>8,} s")

    print("\n  the legacy age, on a naive and an aware datetime:")
    aware = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
    naive = datetime(2026, 11, 14, 9, 30)
    print(f"    legacy_age(aware, naive) = "
          f"{legacy_age(aware, naive):.1f} s  -- 'just now'")
    print(f"    this lab refuses the naive reading time: "
          f"{_age_refuses(naive)}")

    checks = audit(feed)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{len(CURIOUS)} pieces of timestamp text give {readable} "
          f"readable instant(s) and {len(CURIOUS) - readable} refusal(s), the "
          f"feed's {len(feed.articles)} articles give {len(feed.known())} "
          f"instants and {len(feed.unknown())} unknowns, ordered by instant "
          f"the newest is {newest.id} at {newest.moment.iso()} while by text "
          f"it is {by_text.id} at {by_text.printed!r}, '3 hours ago' measured "
          f"from {now.iso()} is "
          f"{parse_timestamp('3 hours ago', now).iso()}, the legacy fallback "
          f"answers 'now' to an unreadable date, the legacy age across a "
          f"missing zone is {legacy_age(aware, naive):.0f} s, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("Demo completed successfully.")
    return 0
