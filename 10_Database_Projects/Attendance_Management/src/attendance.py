"""A timestamp is not a date, and text is not time.

The legacy attendance report asked for a range with a string comparison:

    SELECT p.code, l.stamp FROM logs l JOIN people p ON p.id = l.person_id
    WHERE l.stamp BETWEEN ? AND ?

and passed ('2024-03-01', '2024-03-31'). The column is TEXT holding values
like '2024-03-01 09:05', so the comparison is lexicographic: every check-in on
2024-03-31 reads '2024-03-31 09:10', and that string is *greater* than the
plain date '2024-03-31'. The last day of every range silently disappears -- 3
of the 10 check-ins in the bundled month.

Three more defects fall out of the same confusion:

1. **A month asked for with LIKE '2024-03%' is a string prefix.** A row written
   '2024-3-07 09:15' -- no zero padding on the month -- is invisible to the
   prefix and looks perfectly fine everywhere else.
2. **TEXT order is only date order while the format is fixed.** Sorting
   ['2024-03-06 9:05', '2024-03-06 10:00'] puts 10:00 first, because the
   character '1' sorts before '9'. Zero padding is what makes text sort like
   time, and nothing enforces it inside a TEXT column.
3. **A late-arrival average of 53 minutes over 2 days is 26.5.** ``round()``
   gives 26 (half to even) where a person expects 27, so the average is kept in
   integer minutes and divided half-up.

The fix is to parse each stamp once into a day plus a minute of the day,
compare every range half open -- [start 00:00, day_after(end) 00:00) -- and do
all arithmetic in integer minutes. No float is used anywhere, and no timestamp
is ever compared as text.

The demonstration is offline: the schema lives in ``sqlite3.connect(':memory:')``
and the ten check-ins are seeded from the constants below, so no database file
is needed and two runs print the same bytes.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SAMPLE_FILE = DATA_DIR / "attendance_log.csv"

#: The legacy range, transcribed. It is executable and reproducible.
LEGACY_RANGE = ("SELECT p.code, l.stamp FROM logs l\n"
                "  JOIN people p ON p.id = l.person_id\n"
                " WHERE l.stamp BETWEEN ? AND ?")

#: The legacy month filter, transcribed: a string prefix is not a month.
LEGACY_MONTH = "WHERE l.stamp LIKE ?   -- argument: '2024-03%'"

#: Check-in time that is not late, in minutes from midnight.
GRACE_MINUTES = 9 * 60 + 15
GRACE = "09:15"

#: A stamp that this program accepts: exactly zero padded, exactly one space.
STAMP_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$")

#: A day this program accepts.
DAY_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

#: CSV separator in the bundled log.
FIELD = ","

#: The column names a bundled CSV may carry as its first row.
HEADER = ("code", "full_name", "group", "stamp")

#: The bundled people: code, full name, group.
PEOPLE_SEED = (
    ("STU001", "Aarav Sharma", "Batch A"),
    ("STU002", "Priya Nair", "Batch A"),
    ("STU003", "Rohan Das", "Batch B"),
)

#: The bundled check-ins: code, stamp. Ten rows, three of them on the last day.
LOG_SEED = (
    ("STU001", "2024-03-01 09:05"),
    ("STU001", "2024-03-04 09:35"),
    ("STU001", "2024-03-05 09:48"),
    ("STU001", "2024-03-31 09:10"),
    ("STU002", "2024-03-01 09:20"),
    ("STU002", "2024-03-04 09:02"),
    ("STU002", "2024-03-31 09:12"),
    ("STU003", "2024-03-05 08:55"),
    ("STU003", "2024-03-06 09:40"),
    ("STU003", "2024-03-31 09:00"),
)

SCHEMA_SQL = """
CREATE TABLE people (
    id        INTEGER PRIMARY KEY,
    code      TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    group_name TEXT NOT NULL
);

CREATE TABLE logs (
    id        INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL,
    stamp     TEXT NOT NULL,
    UNIQUE (person_id, stamp),
    FOREIGN KEY (person_id) REFERENCES people (id) ON DELETE CASCADE
);

CREATE INDEX idx_logs_stamp ON logs (stamp);
"""


class DomainError(Exception):
    """A stamp, a day, a range or a row that cannot be honoured, and why."""


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
# A stamp and a day
# --------------------------------------------------------------------------- #
def parse_day(text: str) -> str:
    """`'2024-03-01'` as text, or a refusal -- never a guess at a real date."""
    _text(text, "a day")
    match = DAY_PATTERN.match(text)
    if match is None:
        raise DomainError(f"a day is written YYYY-MM-DD, got {text!r}")
    year, month, day = (int(part) for part in match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        raise DomainError(f"{text!r} is not a day on the calendar") from None


def parse_stamp(text: str) -> str:
    """`'2024-03-01 09:15'` as text, or a refusal.

    The format is fixed on purpose: zero padded, one space, no seconds. A
    database column typed TEXT will accept anything, so the only place the
    rule can live is a parser like this one.
    """
    _text(text, "a stamp")
    match = STAMP_PATTERN.match(text)
    if match is None:
        raise DomainError(f"a stamp is written YYYY-MM-DD HH:MM, got {text!r}")
    year, month, day, hour, minute = (int(part) for part in match.groups())
    try:
        date(year, month, day)
    except ValueError:
        raise DomainError(f"{text!r} is not a day on the calendar") from None
    if hour > 23 or minute > 59:
        raise DomainError(f"{text!r} is not a time on the clock")
    return text


def split_stamp(text: str) -> tuple[str, str]:
    """`'2024-03-01 09:15' -> ('2024-03-01', '09:15')` -- a date and a time."""
    parse_stamp(text)
    day, clock = text.split(" ", 1)
    return day, clock


def day_of(text: str) -> str:
    """Only the date part of a timestamp, with the time dropped."""
    return split_stamp(text)[0]


def clock_of(text: str) -> str:
    """Only the time part of a timestamp, as `HH:MM`."""
    return split_stamp(text)[1]


def minutes_of(clock: str) -> int:
    """`'09:42' -> 582`; the minute of the day, as a whole number."""
    _text(clock, "a time")
    match = re.match(r"^(\d{2}):(\d{2})$", clock)
    if match is None:
        raise DomainError(f"a time is written HH:MM, got {clock!r}")
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        raise DomainError(f"{clock!r} is not a time on the clock")
    return hour * 60 + minute


def minutes_of_stamp(text: str) -> int:
    """The minute of the day a check-in happened at."""
    return minutes_of(clock_of(text))


def day_after(text: str) -> str:
    """The next calendar day: `'2024-03-31' -> '2024-04-01'`."""
    return (date.fromisoformat(parse_day(text)) + timedelta(days=1)).isoformat()


def range_bounds(start: str, end: str) -> tuple[str, str]:
    """The half-open text bounds a range needs: `[start 00:00, end + 1 00:00)`.

    The upper bound is the *next* day at midnight, so a check-in at
    '2024-03-31 23:59' is inside a range that ends on 2024-03-31 and the
    comparison stays a comparison of strings that happen to be zero padded.
    """
    low = f"{parse_day(start)} 00:00"
    high = f"{day_after(end)} 00:00"
    if low >= high:
        raise DomainError(f"a range starts before it ends, got {start!r} "
                          f"to {end!r}")
    return low, high


def legacy_bounds(start: str, end: str) -> tuple[str, str]:
    """The legacy bounds: the bare dates, compared against a full timestamp."""
    return parse_day(start), parse_day(end)


# --------------------------------------------------------------------------- #
# Late arrival, in integer minutes
# --------------------------------------------------------------------------- #
def late_minutes(stamp: str, grace: str = GRACE) -> int:
    """Minutes after `grace`, or 0. `09:42` against a `09:15` grace is 27."""
    arrival = minutes_of_stamp(stamp)
    allowed = minutes_of(grace)
    if arrival <= allowed:
        return 0
    return arrival - allowed


def average_late_minutes(total_minutes: int, late_sessions: int) -> int:
    """The mean late arrival, in whole minutes, rounded half-up."""
    _whole(total_minutes, "a total of minutes")
    _whole(late_sessions, "a number of sessions")
    if total_minutes < 0:
        raise DomainError(f"a total of minutes is not negative, got {total_minutes}")
    if late_sessions < 0:
        raise DomainError(f"a number of sessions is not negative, got {late_sessions}")
    if late_sessions == 0:
        return 0
    return divide_half_up(total_minutes, late_sessions)


def legacy_average_late_minutes(total_minutes: int, late_sessions: int) -> int:
    """`round(total / sessions)` -- half to even, so 26.5 becomes 26."""
    if late_sessions == 0:
        return 0
    return round(total_minutes / late_sessions)


# --------------------------------------------------------------------------- #
# Ordering
# --------------------------------------------------------------------------- #
def sort_stamps(stamps) -> list[str]:
    """Every stamp parsed and ordered by its real minute, not by its letters."""
    held = list(stamps)
    for stamp in held:
        parse_stamp(stamp)
    return sorted(held, key=lambda stamp: (day_of(stamp), minutes_of_stamp(stamp)))


def legacy_sort_stamps(stamps) -> list[str]:
    """`sorted(stamps)` -- text order, which needs zero padding to be time order."""
    return sorted(list(stamps))


def month_rows(conn: sqlite3.Connection, month: str) -> list[tuple[str, str]]:
    """The check-ins of a month like `'2024-03'`, asked for by its real month."""
    _text(month, "a month")
    match = re.match(r"^(\d{4})-(\d{2})$", month)
    if match is None:
        raise DomainError(f"a month is written YYYY-MM, got {month!r}")
    if not 1 <= int(match.group(2)) <= 12:
        raise DomainError(f"{month!r} is not a month of the year")
    rows = conn.execute(
        "SELECT p.code, l.stamp FROM logs l JOIN people p ON p.id = l.person_id "
        "WHERE substr(l.stamp, 1, 7) = ? ORDER BY l.stamp, p.code",
        (month,),
    ).fetchall()
    return [(row[0], row[1]) for row in rows]


def prefix_rows(stamps, month: str) -> list[str]:
    """The legacy month: `LIKE '2024-03%'`, which is a string prefix."""
    _text(month, "a month")
    return [stamp for stamp in stamps if stamp.startswith(month)]


def parsed_month_rows(stamps, month: str) -> list[str]:
    """The same question asked of parsed values: malformed rows are refused."""
    _text(month, "a month")
    return [stamp for stamp in stamps if split_stamp(stamp)[0][:7] == month]


# --------------------------------------------------------------------------- #
# The database
# --------------------------------------------------------------------------- #
def build_database(people=None, logs=None) -> sqlite3.Connection:
    """An in-memory database, seeded from the constants unless told otherwise.

    No file, no data directory, no leftover state: every call starts from the
    same three people and the same ten check-ins, in the same order.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)

    for code, full_name, group_name in (PEOPLE_SEED if people is None else people):
        _text(code, "a person code")
        _text(full_name, "a name")
        _text(group_name, "a group")
        conn.execute(
            "INSERT INTO people (code, full_name, group_name) VALUES (?, ?, ?)",
            (code, full_name, group_name),
        )

    for code, stamp in (LOG_SEED if logs is None else logs):
        insert_log(conn, code, stamp, commit=False)

    conn.commit()
    return conn


def insert_log(conn: sqlite3.Connection, code: str, stamp: str, *,
               commit: bool = True) -> int:
    """Insert one check-in for one person code; a duplicate is refused."""
    parse_stamp(stamp)
    row = conn.execute("SELECT id FROM people WHERE code = ?", (code,)).fetchone()
    if row is None:
        raise DomainError(f"no person with the code {code!r}")
    try:
        cursor = conn.execute(
            "INSERT INTO logs (person_id, stamp) VALUES (?, ?)", (row[0], stamp))
    except sqlite3.IntegrityError:
        raise DomainError(f"{code!r} already has a check-in at {stamp!r}") from None
    if commit:
        conn.commit()
    return int(cursor.lastrowid)


def logs_between(conn: sqlite3.Connection, start: str, end: str) -> list[tuple[str, str, str]]:
    """Every check-in in `[start, end]`, compared half open."""
    low, high = range_bounds(start, end)
    rows = conn.execute(
        "SELECT p.code, p.full_name, l.stamp FROM logs l "
        "JOIN people p ON p.id = l.person_id "
        "WHERE l.stamp >= ? AND l.stamp < ? ORDER BY l.stamp, p.code",
        (low, high),
    ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def legacy_logs_between(conn: sqlite3.Connection,
                        start: str, end: str) -> list[tuple[str, str, str]]:
    """The legacy range: `BETWEEN '2024-03-01' AND '2024-03-31'` on TEXT."""
    low, high = legacy_bounds(start, end)
    rows = conn.execute(
        "SELECT p.code, p.full_name, l.stamp FROM logs l "
        "JOIN people p ON p.id = l.person_id "
        "WHERE l.stamp BETWEEN ? AND ? ORDER BY l.stamp, p.code",
        (low, high),
    ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def late_report(conn: sqlite3.Connection, start: str, end: str) -> list[dict]:
    """Per person, over one range: days, late days, late minutes, mean."""
    totals: dict[str, dict] = {}
    for code, full_name, stamp in sorted(logs_between(conn, start, end)):
        held = totals.setdefault(code, {"code": code, "full_name": full_name,
                                        "days": 0, "late_days": 0,
                                        "late_minutes": 0})
        held["days"] += 1
        minutes = late_minutes(stamp)
        if minutes:
            held["late_days"] += 1
            held["late_minutes"] += minutes
        else:
            held["late_minutes"] += 0
    report = []
    for code in sorted(totals):
        held = totals[code]
        held["average"] = average_late_minutes(held["late_minutes"],
                                               held["late_days"])
        held["legacy_average"] = legacy_average_late_minutes(
            held["late_minutes"], held["late_days"])
        report.append(held)
    return report


def orphan_logs(conn: sqlite3.Connection) -> int:
    """Check-ins whose person is missing -- impossible while the key holds."""
    row = conn.execute(
        "SELECT COUNT(*) FROM logs l LEFT JOIN people p ON p.id = l.person_id "
        "WHERE p.id IS NULL").fetchone()
    return int(row[0])


# --------------------------------------------------------------------------- #
# Reading the bundled log
# --------------------------------------------------------------------------- #
def parse_log(text: str):
    """Read `code, full_name, group, stamp` per line; `#` starts a comment.

    A first line that names those four columns is a header and is skipped, so
    the same file can be opened in a spreadsheet.
    """
    people: dict[str, tuple[str, str, str]] = {}
    logs: list[tuple[str, str]] = []
    seen_row = False
    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        body = line.split("#", 1)[0].strip()
        if not body:
            continue
        fields = [field.strip() for field in body.split(FIELD)]
        if not seen_row and tuple(fields) == HEADER:
            continue
        seen_row = True
        if len(fields) != 4:
            raise DomainError(f"line {number}: four fields are needed -- a code, "
                              f"a name, a group and a stamp -- got {len(fields)}")
        code, full_name, group_name, stamp = fields
        if not code or not full_name or not group_name:
            raise DomainError(f"line {number}: a code, a name and a group are "
                              f"all required")
        try:
            parse_stamp(stamp)
        except DomainError as error:
            raise DomainError(f"line {number}: {error}") from None
        known = people.get(code)
        if known is None:
            people[code] = (code, full_name, group_name)
        elif known[1:] != (full_name, group_name):
            raise DomainError(f"line {number}: {code!r} is already named "
                              f"{known[1]!r} in {known[2]!r}")
        if (code, stamp) in logs:
            raise DomainError(f"line {number}: {code!r} checks in twice at "
                              f"{stamp!r}")
        logs.append((code, stamp))
    if not logs:
        raise DomainError("a log needs at least one check-in")
    return tuple(people[code] for code in people), tuple(logs)


def read_log(path=None):
    """Read the bundled log (or `path`) as `(people, check-ins)`."""
    target = Path(SAMPLE_FILE if path is None else path)
    if not target.is_file():
        raise DomainError(f"file not found: {target}")
    return parse_log(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(measured: dict, make_database=build_database) -> list[tuple[str, bool]]:
    """Twelve checks, each re-derived from a measurement or a fresh database."""
    def at(name: str):
        if name not in measured:
            raise DomainError(f"no measurement named {name!r}")
        return measured[name]

    def a_stamp_keeps_its_time() -> bool:
        return at("date_part") == "2024-03-01" and \
            at("clock_part") == "09:15" and \
            at("stamp_is_not_its_date") is True

    def a_text_range_drops_the_last_day() -> bool:
        return at("legacy_rows") == 7 and at("rows") == 10 and \
            at("legacy_rows") < at("rows")

    def the_last_day_is_what_the_text_range_loses() -> bool:
        return at("last_day_legacy") == 0 and at("last_day_correct") == 3

    def a_month_is_not_a_string_prefix() -> bool:
        return at("prefix_month") == 1 and at("parsed_month") == 0 and \
            at("malformed_refused") is True

    def only_a_zero_padded_stamp_parses() -> bool:
        return at("padded_ok") is True and at("unpadded_refused") is True

    def text_order_is_not_time_order() -> bool:
        return at("legacy_order") == ["2024-03-06 10:00", "2024-03-06 9:05"] \
            and at("order") == ["2024-03-06 09:05", "2024-03-06 10:00"] \
            and at("unpadded_refused") is True

    def late_minutes_are_minutes_from_the_grace_time() -> bool:
        return at("late_942") == 27 and at("late_915") == 0 and \
            at("late_914") == 0

    def a_late_average_is_divided_half_up() -> bool:
        return at("average_53_2") == 27 and at("legacy_average_53_2") == 26

    def the_report_adds_up_to_the_stamps() -> bool:
        report = at("report")
        return sum(row["days"] for row in report) == at("rows") and \
            sum(row["late_minutes"] for row in report) == at("late_total") and \
            at("late_total") == 83 and at("late_days") == 4

    def every_check_in_belongs_to_a_person() -> bool:
        conn = make_database()
        try:
            return orphan_logs(conn) == 0 and \
                int(conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]) == 10
        finally:
            conn.close()

    def the_day_after_the_end_of_a_month() -> bool:
        return at("after_march") == "2024-04-01" and \
            at("after_december") == "2025-01-01" and \
            at("after_leap_day") == "2024-03-01"

    def a_rebuilt_database_counts_the_same() -> bool:
        conn = make_database()
        try:
            return len(logs_between(conn, "2024-03-01", "2024-03-31")) == \
                at("rows")
        finally:
            conn.close()

    checks = [
        ("a stamp keeps its time", a_stamp_keeps_its_time),
        ("a text range drops the last day", a_text_range_drops_the_last_day),
        ("the last day is what the text range loses",
         the_last_day_is_what_the_text_range_loses),
        ("a month is not a string prefix", a_month_is_not_a_string_prefix),
        ("only a zero padded stamp parses", only_a_zero_padded_stamp_parses),
        ("text order is not time order", text_order_is_not_time_order),
        ("late minutes are minutes from the grace time",
         late_minutes_are_minutes_from_the_grace_time),
        ("a late average is divided half up", a_late_average_is_divided_half_up),
        ("the report adds up to the stamps", the_report_adds_up_to_the_stamps),
        ("every check in belongs to a person",
         every_check_in_belongs_to_a_person),
        ("the day after the end of a month", the_day_after_the_end_of_a_month),
        ("a rebuilt database counts the same",
         a_rebuilt_database_counts_the_same),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def measure(conn: sqlite3.Connection) -> dict:
    """Every number the audit is allowed to read, measured once."""
    measured: dict = {}
    stamp = "2024-03-01 09:15"
    measured["date_part"] = day_of(stamp)
    measured["clock_part"] = clock_of(stamp)
    measured["stamp_is_not_its_date"] = stamp != day_of(stamp)

    measured["rows"] = len(logs_between(conn, "2024-03-01", "2024-03-31"))
    measured["legacy_rows"] = len(legacy_logs_between(conn, "2024-03-01",
                                                      "2024-03-31"))
    measured["last_day_correct"] = len(logs_between(conn, "2024-03-31",
                                                    "2024-03-31"))
    measured["last_day_legacy"] = len(legacy_logs_between(conn, "2024-03-31",
                                                          "2024-03-31"))

    mixed = ["2024-03-01 09:15", "2024-3-07 09:15"]
    measured["prefix_month"] = len(prefix_rows(mixed, "2024-03"))
    try:
        measured["parsed_month"] = len(parsed_month_rows(mixed, "2024-03"))
    except DomainError:
        measured["parsed_month"] = 0
    try:
        parse_stamp("2024-3-07 09:15")
    except DomainError:
        measured["malformed_refused"] = True
    else:
        measured["malformed_refused"] = False

    try:
        parse_stamp("2024-03-07 09:15")
    except DomainError:
        measured["padded_ok"] = False
    else:
        measured["padded_ok"] = True
    try:
        parse_stamp("2024-3-07 09:15")
    except DomainError:
        measured["unpadded_refused"] = True
    else:
        measured["unpadded_refused"] = False

    pair = ["2024-03-06 9:05", "2024-03-06 10:00"]
    measured["legacy_order"] = legacy_sort_stamps(pair)
    measured["order"] = sort_stamps(["2024-03-06 10:00", "2024-03-06 09:05"])

    measured["late_942"] = late_minutes("2024-03-04 09:42")
    measured["late_915"] = late_minutes("2024-03-04 09:15")
    measured["late_914"] = late_minutes("2024-03-04 09:14")
    measured["average_53_2"] = average_late_minutes(53, 2)
    measured["legacy_average_53_2"] = legacy_average_late_minutes(53, 2)

    measured["report"] = late_report(conn, "2024-03-01", "2024-03-31")
    measured["late_total"] = sum(row["late_minutes"]
                                 for row in measured["report"])
    measured["late_days"] = sum(row["late_days"] for row in measured["report"])

    measured["after_march"] = day_after("2024-03-31")
    measured["after_december"] = day_after("2024-12-31")
    measured["after_leap_day"] = day_after("2024-02-29")
    return measured


def run_demo() -> int:
    conn = build_database()
    try:
        measured = measure(conn)
        rows = logs_between(conn, "2024-03-01", "2024-03-31")

        print("=" * 78)
        print(" ATTENDANCE LAB - a timestamp is not a date")
        print("=" * 78)

        print("\n  the legacy range, transcribed:")
        for line in LEGACY_RANGE.split("\n"):
            print(f"    {line}")
        print("  called with ('2024-03-01', '2024-03-31')")

        print(f"\n  March 2024 holds {measured['rows']} check-ins for "
              f"{len(measured['report'])} people:")
        print(f"    the legacy BETWEEN reads:  {measured['legacy_rows']} rows")
        print(f"    the same range, half open: {measured['rows']} rows")
        print(f"    check-ins on the last day: {measured['last_day_correct']}, "
              f"of which the legacy range sees {measured['last_day_legacy']}")
        print("    '2024-03-31 09:10' > '2024-03-31' as text, every time")

        print("\n  a month is not a string prefix:")
        print(f"    LIKE '2024-03%' matches {measured['prefix_month']} of 2 "
              f"rows in ['2024-03-01 09:15', '2024-3-07 09:15']")
        print(f"    parsing the month matches {measured['parsed_month']} and "
              f"refuses the unpadded one")

        print("\n  text order is not time order:")
        print(f"    sorted():     {', '.join(measured['legacy_order'])}")
        print(f"    by the clock: {', '.join(measured['order'])}")
        print("    and the unpadded '9:05' is refused outright, because a")
        print("    column of text cannot promise that the format is fixed")

        print("\n  late arrival, in whole minutes from " + GRACE + ":")
        print(f"    09:42 -> {measured['late_942']} minutes late, "
              f"09:15 -> {measured['late_915']}, 09:14 -> {measured['late_914']}")
        print(f"    {'code':<8}{'name':<16}{'days':>5}{'late':>6}"
              f"{'minutes':>9}{'mean':>6}")
        for row in measured["report"]:
            print(f"    {row['code']:<8}{row['full_name']:<16}"
                  f"{row['days']:>5}{row['late_days']:>6}"
                  f"{row['late_minutes']:>9}{row['average']:>6}")
        print(f"    all {measured['late_total']} late minutes over "
              f"{measured['late_days']} late days; STU001 is 53 over 2, which "
              f"is 26.5 -> {measured['average_53_2']} here and "
              f"{measured['legacy_average_53_2']} from round()")

        checks = audit(measured, make_database=build_database)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

        print()
        print("Cross-checks OK: " +
              f"{len(rows)} check-ins in March 2024, the legacy BETWEEN reads "
              f"{measured['legacy_rows']} because "
              f"'2024-03-31 09:10' sorts after '2024-03-31', the three "
              f"check-ins on the last day vanish, LIKE '2024-03%' hides the "
              f"unpadded '2024-3-07 09:15' that parsing refuses, "
              f"09:42 is {measured['late_942']} minutes late against a "
              f"{GRACE} grace, 53 late minutes over 2 days is "
              f"{measured['average_53_2']} half-up and "
              f"{measured['legacy_average_53_2']} under round(), and "
              f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks "
              f"hold")
        print("Demo completed successfully.")
        return 0
    finally:
        conn.close()
