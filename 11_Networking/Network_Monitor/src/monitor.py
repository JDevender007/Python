"""Uptime is measured in seconds, not in transitions.

The legacy availability report reads a state-change log and counts rows:

    uptime = round(100 * sum(1 for row in rows if row["state"] == "up")
                   / len(rows), 1)

Two things are wrong with that one expression, and the errant number looks
perfectly reasonable on a dashboard.

**1. A transition is not a duration.** Each row marks the moment the service
changed state, so a forty-five second blip and an eight-hour outage each cost
exactly one row. In the bundled log the service is *up* for 600 seconds and
*down* for 9400 seconds out of a 10000-second window -- 6.00% availability --
yet three of the six transitions say `up`, so the legacy report prints 50.0%.

**2. The last interval has no following event, so a pairwise loop drops it.**
The natural way to turn transitions into durations is

    for current, following in zip(rows, rows[1:]):
        record(current.state, following.changed_at_s - current.changed_at_s)

which never records the state that is still in force when the window closes.
In the bundled log that silently deletes the final 300 seconds of downtime:
the covered span becomes 9700 seconds instead of 10000 and availability is
reported as 6.19% rather than 6.00%. The window's end is an event.

The rebuild turns the log into half-open intervals that tile the window exactly,
refuses a log that does not start at the window's start, a log whose states do
not alternate, and a transition outside the window. Durations are integer
seconds, percentages are basis points with `divide_half_up`, and MTTR and MTBF
are computed from the intervals rather than from row counts.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WINDOW_FILE = DATA_DIR / "window.csv"
CHANGES_FILE = DATA_DIR / "state_changes.csv"

STATES = ("up", "down")
OPPOSITE = {"up": "down", "down": "up"}

#: The legacy availability expression, transcribed so the demo can print it.
LEGACY_UPTIME = (
    'uptime = round(100 * sum(1 for row in rows if row["state"] == "up")'
    " / len(rows), 1)"
)

#: The legacy interval loop, which never records the state in force at the end.
LEGACY_INTERVALS = (
    "for current, following in zip(rows, rows[1:]):\n"
    "    record(current.state, following.changed_at_s - current.changed_at_s)"
)


class MonitorError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise MonitorError(f"{name} must be text, got {type(value).__name__}")
    if not value.strip():
        raise MonitorError(f"{name} must not be empty")
    return value


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MonitorError(f"{name} must be an integer, got {type(value).__name__}")
    return value


def _non_negative(value: object, name: str) -> int:
    number = _whole(value, name)
    if number < 0:
        raise MonitorError(f"{name} must not be negative, got {number}")
    return number


def _positive(value: object, name: str) -> int:
    number = _whole(value, name)
    if number <= 0:
        raise MonitorError(f"{name} must be positive, got {number}")
    return number


def divide_half_up(numerator: int, denominator: int) -> int:
    """Integer division rounding halves away from zero, with no float."""
    top = _whole(numerator, "numerator")
    bottom = _positive(denominator, "denominator")
    sign = -1 if top < 0 else 1
    magnitude = abs(top)
    return sign * ((magnitude * 2 + bottom) // (2 * bottom))


def state_of(text: str) -> str:
    """Normalise and validate a state label."""
    raw = _text(text, "state").strip().lower()
    if raw not in STATES:
        raise MonitorError(f"state must be one of {list(STATES)}, got {raw!r}")
    return raw


def format_bp(basis_points: int) -> str:
    """Render hundredths of a percent as a two-place percentage."""
    value = _whole(basis_points, "basis_points")
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    return f"{sign}{magnitude // 100}.{magnitude % 100:02d}"


def _int(text: str, name: str) -> int:
    raw = _text(text, name).strip()
    try:
        return int(raw, 10)
    except ValueError as exc:
        raise MonitorError(f"{name} must be a whole number, got {raw!r}") from exc


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Window:
    """The half-open period the monitor is asked about: [start_s, end_s)."""

    start_s: int
    end_s: int

    @property
    def seconds(self) -> int:
        return self.end_s - self.start_s


@dataclass(frozen=True)
class Transition:
    """One row of the state-change log."""

    seq: int
    at_s: int
    state: str
    note: str


@dataclass(frozen=True)
class Interval:
    """A state held over the half-open range [start_s, end_s)."""

    state: str
    start_s: int
    end_s: int

    @property
    def seconds(self) -> int:
        return self.end_s - self.start_s


def _read_rows(path: str | Path, required: Sequence[str]) -> list[dict[str, str]]:
    target = Path(path)
    if not target.is_file():
        raise MonitorError(f"file not found: {target.name}")
    with target.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = [column for column in required if column not in header]
        if missing:
            raise MonitorError(f"{target.name} is missing column(s): {', '.join(missing)}")
        return [dict(row) for row in reader]


def load_window(path: str | Path | None = None) -> Window:
    rows = _read_rows(path or WINDOW_FILE, ("start_s", "end_s"))
    if len(rows) != 1:
        raise MonitorError(f"window.csv must hold exactly one row, got {len(rows)}")
    start = _non_negative(_int(rows[0]["start_s"], "start_s"), "start_s")
    end = _non_negative(_int(rows[0]["end_s"], "end_s"), "end_s")
    if end <= start:
        raise MonitorError(f"window end_s {end} must be greater than start_s {start}")
    return Window(start_s=start, end_s=end)


def load_changes(path: str | Path | None = None) -> list[Transition]:
    rows = _read_rows(path or CHANGES_FILE, ("seq", "changed_at_s", "state", "note"))
    if not rows:
        raise MonitorError("state_changes.csv holds no transitions")
    changes: list[Transition] = []
    for row in rows:
        changes.append(
            Transition(
                seq=_positive(_int(row["seq"], "seq"), "seq"),
                at_s=_non_negative(_int(row["changed_at_s"], "changed_at_s"), "changed_at_s"),
                state=state_of(row["state"]),
                note=_text(row["note"], "note").strip(),
            )
        )
    if len({change.seq for change in changes}) != len(changes):
        raise MonitorError("seq values must be unique")
    ordered = sorted(changes, key=lambda change: change.at_s)
    if ordered != changes:
        raise MonitorError("transitions must be listed in changed_at_s order")
    return changes


# --------------------------------------------------------------------------- #
# The correct construction
# --------------------------------------------------------------------------- #
def build_intervals(window: Window, changes: Sequence[Transition]) -> list[Interval]:
    """Turn a transition log into intervals that tile the window exactly.

    The window's end is an event: the state in force at the last transition holds
    until `window.end_s`. That tail is the interval a pairwise loop forgets.
    """
    start = _whole(window.start_s, "start_s")
    end = _whole(window.end_s, "end_s")
    if end <= start:
        raise MonitorError(f"window end_s {end} must be greater than start_s {start}")
    rows = list(changes)
    if not rows:
        raise MonitorError("a transition log needs at least one row")
    if rows[0].at_s != start:
        raise MonitorError(
            f"the first transition is at {rows[0].at_s}, not at the window start {start}"
        )
    for index, change in enumerate(rows):
        if not start <= change.at_s < end:
            raise MonitorError(
                f"transition {change.seq} at {change.at_s} is outside the window [{start}, {end})"
            )
        if index and change.at_s <= rows[index - 1].at_s:
            raise MonitorError(
                f"transition {change.seq} at {change.at_s} does not follow "
                f"transition {rows[index - 1].seq} at {rows[index - 1].at_s}"
            )
        if index and change.state != OPPOSITE[rows[index - 1].state]:
            raise MonitorError(
                f"transition {change.seq} repeats the state {change.state!r}; "
                "a state-change log must alternate"
            )
    intervals: list[Interval] = []
    for index, change in enumerate(rows):
        next_start = rows[index + 1].at_s if index + 1 < len(rows) else end
        intervals.append(Interval(state=change.state, start_s=change.at_s, end_s=next_start))
    return intervals


def legacy_intervals(window: Window, changes: Sequence[Transition]) -> list[Interval]:
    """The pairwise loop, executed as written: the last state's tail is dropped."""
    rows = build_intervals(window, changes)
    return rows[:-1] if len(rows) > 1 else []


def totals(intervals: Sequence[Interval]) -> dict[str, int]:
    """Seconds held in each state."""
    result = {"up": 0, "down": 0}
    for interval in intervals:
        if interval.state not in result:
            raise MonitorError(f"unknown state in an interval: {interval.state!r}")
        result[interval.state] += interval.seconds
    return result


def uptime_bp(intervals: Sequence[Interval], window: Window) -> int:
    """Availability as basis points of the window's length."""
    seconds = _positive(window.seconds, "window length")
    up = totals(intervals)["up"]
    return divide_half_up(up * 10_000, seconds)


def uptime_over_covered_bp(intervals: Sequence[Interval]) -> int:
    """Availability as basis points of the time actually covered by intervals."""
    held = totals(intervals)
    covered = held["up"] + held["down"]
    if covered == 0:
        raise MonitorError("no interval covers any time")
    return divide_half_up(held["up"] * 10_000, covered)


def legacy_uptime_bp(changes: Sequence[Transition]) -> int:
    """The legacy expression: up rows over all rows."""
    rows = list(changes)
    if not rows:
        raise MonitorError("a transition log needs at least one row")
    up = sum(1 for row in rows if row.state == "up")
    return divide_half_up(up * 10_000, len(rows))


def mttr_s(intervals: Sequence[Interval]) -> int:
    """Mean time to recover: total downtime over the number of outages."""
    held = totals(intervals)
    outages = sum(1 for interval in intervals if interval.state == "down")
    if outages == 0:
        return 0
    return divide_half_up(held["down"], outages)


def mtbf_s(intervals: Sequence[Interval]) -> int:
    """Mean time between failures: total uptime over the number of recoveries."""
    held = totals(intervals)
    recoveries = sum(1 for interval in intervals if interval.state == "up")
    if recoveries == 0:
        return 0
    return divide_half_up(held["up"], recoveries)


def longest_outage_s(intervals: Sequence[Interval]) -> int:
    return max(
        (interval.seconds for interval in intervals if interval.state == "down"),
        default=0,
    )


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(
    changes_path: str | Path | None = None,
    *,
    window_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load the window and the log, build the intervals, collect every number."""
    if changes_path is not None:
        folder = Path(changes_path).resolve().parent
        window_path = window_path or folder / "window.csv"
    window = load_window(window_path)
    changes = load_changes(changes_path)
    intervals = build_intervals(window, changes)
    held = totals(intervals)
    legacy_rows = legacy_intervals(window, changes)
    return {
        "window": window,
        "changes": changes,
        "intervals": intervals,
        "totals": held,
        "uptime_bp": uptime_bp(intervals, window),
        "legacy_bp": legacy_uptime_bp(changes),
        "legacy_intervals": legacy_rows,
        "legacy_covered_s": sum(interval.seconds for interval in legacy_rows),
        "legacy_uptime_bp": uptime_over_covered_bp(legacy_rows) if legacy_rows else 0,
        "mttr_s": mttr_s(intervals),
        "mtbf_s": mtbf_s(intervals),
        "longest_outage_s": longest_outage_s(intervals),
        "outages": sum(1 for interval in intervals if interval.state == "down"),
        "up_rows": sum(1 for change in changes if change.state == "up"),
    }


def report(measured: dict[str, Any]) -> dict[str, Any]:
    window = measured["window"]
    held = measured["totals"]
    return {
        "window_start_s": window.start_s,
        "window_end_s": window.end_s,
        "window_s": window.seconds,
        "transitions": len(measured["changes"]),
        "up_transitions": measured["up_rows"],
        "outages": measured["outages"],
        "intervals": [
            {"state": interval.state, "start_s": interval.start_s, "end_s": interval.end_s}
            for interval in measured["intervals"]
        ],
        "up_s": held["up"],
        "down_s": held["down"],
        "uptime_bp": measured["uptime_bp"],
        "uptime_percent": format_bp(measured["uptime_bp"]),
        "legacy_bp": measured["legacy_bp"],
        "legacy_percent": format_bp(measured["legacy_bp"]),
        "legacy_covered_s": measured["legacy_covered_s"],
        "legacy_uptime_bp": measured["legacy_uptime_bp"],
        "legacy_uptime_percent": format_bp(measured["legacy_uptime_bp"]),
        "mttr_s": measured["mttr_s"],
        "mtbf_s": measured["mtbf_s"],
        "longest_outage_s": measured["longest_outage_s"],
    }


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:
        return False


def _refuses(call) -> bool:
    try:
        call()
    except MonitorError:
        return True
    return False


def audit(
    measured: dict[str, Any],
    *,
    read_intervals: Callable[[Window, Sequence[Transition]], list[Interval]] = build_intervals,
) -> list[tuple[str, bool]]:
    """Every check compares a measured number with an independent computation."""
    window = measured["window"]
    changes = measured["changes"]
    held = measured["totals"]
    intervals = measured["intervals"]

    def intervals_via_reader() -> list[Interval]:
        return read_intervals(window, changes)

    def independent_up_seconds() -> int:
        total = 0
        for index, change in enumerate(changes):
            next_at = changes[index + 1].at_s if index + 1 < len(changes) else window.end_s
            if change.state == "up":
                total += next_at - change.at_s
        return total

    checks = [
        (
            "intervals_tile_the_window_exactly",
            lambda: sum(interval.seconds for interval in intervals_via_reader()) == window.seconds,
        ),
        (
            "intervals_alternate_and_start_at_the_window",
            lambda: intervals_via_reader()[0].start_s == window.start_s
            and all(
                pair.state != interval.state
                for pair, interval in zip(intervals_via_reader(), intervals_via_reader()[1:])
            ),
        ),
        (
            "up_seconds_match_an_independent_loop",
            lambda: held["up"] == independent_up_seconds(),
        ),
        (
            "up_seconds_are_pinned",
            lambda: held["up"] == 600,
        ),
        (
            "down_seconds_are_pinned",
            lambda: held["down"] == 9400,
        ),
        (
            "up_and_down_account_for_the_whole_window",
            lambda: held["up"] + held["down"] == window.seconds == 10_000,
        ),
        (
            "uptime_is_six_percent",
            lambda: measured["uptime_bp"] == 600 and format_bp(measured["uptime_bp"]) == "6.00",
        ),
        (
            "the_legacy_report_counts_rows",
            lambda: measured["legacy_bp"] == 5000
            and format_bp(measured["legacy_bp"]) == "50.00"
            and measured["up_rows"] == 3
            and len(changes) == 6,
        ),
        (
            "the_row_count_overstates_availability_by_44_points",
            lambda: measured["legacy_bp"] - measured["uptime_bp"] == 4400,
        ),
        (
            "the_pairwise_loop_drops_the_final_interval",
            lambda: measured["legacy_covered_s"] == 9700
            and window.seconds - measured["legacy_covered_s"] == intervals[-1].seconds == 300,
        ),
        (
            "the_dropped_tail_changes_the_percentage",
            lambda: measured["legacy_uptime_bp"] == 619
            and format_bp(measured["legacy_uptime_bp"]) == "6.19",
        ),
        (
            "mttr_divides_downtime_by_outages",
            lambda: measured["mttr_s"] == 3133 == divide_half_up(held["down"], measured["outages"]),
        ),
        (
            "mtbf_divides_uptime_by_recoveries",
            lambda: measured["mtbf_s"] == 200 == divide_half_up(held["up"], 3),
        ),
        (
            "there_are_three_outages_and_one_is_the_longest",
            lambda: measured["outages"] == 3 and measured["longest_outage_s"] == 8700,
        ),
        (
            "a_repeated_state_is_refused",
            lambda: _refuses(
                lambda: build_intervals(
                    window, [Transition(1, 0, "up", ""), Transition(2, 5, "up", "")]
                )
            ),
        ),
        (
            "a_late_first_transition_is_refused",
            lambda: _refuses(
                lambda: build_intervals(window, [Transition(1, 1, "up", "")])
            ),
        ),
        (
            "a_transition_at_the_window_end_is_refused",
            lambda: _refuses(
                lambda: build_intervals(
                    window, [Transition(1, 0, "up", ""), Transition(2, 10_000, "down", "")]
                )
            ),
        ),
        (
            "rebuild_is_deterministic",
            lambda: intervals_via_reader() == intervals,
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def render_intervals(measured: dict[str, Any]) -> str:
    window = measured["window"]
    lines = ["  state   start_s    end_s   seconds   share"]
    for interval in measured["intervals"]:
        share = divide_half_up(interval.seconds * 10_000, window.seconds)
        lines.append(
            f"  {interval.state:<8}{interval.start_s:>8}{interval.end_s:>9}"
            f"{interval.seconds:>10}{format_bp(share):>9}%"
        )
    held = measured["totals"]
    lines.append(
        f"  {'TOTAL':<8}{window.start_s:>8}{window.end_s:>9}"
        f"{window.seconds:>10}{'100.00':>9}%"
    )
    lines.append(
        f"  up {held['up']} s, down {held['down']} s, {measured['outages']} outages"
    )
    return "\n".join(lines)


def run_demo() -> int:
    measured = measure()
    window = measured["window"]
    held = measured["totals"]
    print("Network monitor -- uptime is time, not transitions")
    print("=" * 51)
    print()
    print(
        f"Window: {window.start_s}..{window.end_s} s ({window.seconds} s), "
        f"{len(measured['changes'])} state changes."
    )
    print()
    print(render_intervals(measured))
    print()
    print("1. A transition is not a duration.")
    print("   " + LEGACY_UPTIME)
    print(
        f"   {measured['up_rows']} of {len(measured['changes'])} rows say 'up', so the "
        f"legacy report prints {format_bp(measured['legacy_bp'])}%."
    )
    print(
        f"   The service was up for {held['up']} s of {window.seconds} s, which is "
        f"{format_bp(measured['uptime_bp'])}%."
    )
    print(
        f"   Two long outages weigh the same as two short ones in that ratio: the "
        f"longest down interval is {measured['longest_outage_s']} s."
    )
    print()
    print("2. The state in force at the window's end is still an interval.")
    print("   " + LEGACY_INTERVALS.replace("\n", "\n   "))
    print(
        f"   The pairwise loop covers {measured['legacy_covered_s']} s of "
        f"{window.seconds} s, losing the final {window.seconds - measured['legacy_covered_s']} s,"
    )
    print(
        f"   and reports {format_bp(measured['legacy_uptime_bp'])}% over what it did cover."
    )
    print()
    print(
        f"MTTR {measured['mttr_s']} s = {held['down']} s / {measured['outages']} outages; "
        f"MTBF {measured['mtbf_s']} s = {held['up']} s / 3 recoveries."
    )
    print()
    print("Checks")
    results = audit(measured)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    passed = sum(1 for _, ok in results if ok)
    print(f"  {passed}/{len(results)} checks pass")
    print()
    print(
        "Cross-checks OK: the window runs "
        f"{window.start_s}..{window.end_s} s and the {len(measured['changes'])} transitions "
        f"tile it into {len(measured['intervals'])} intervals -- {held['up']} s up and "
        f"{held['down']} s down, {format_bp(measured['uptime_bp'])}% availability -- while the "
        f"legacy row count sees {measured['up_rows']} of {len(measured['changes'])} rows 'up' "
        f"and prints {format_bp(measured['legacy_bp'])}%, overstating it by "
        f"{format_bp(measured['legacy_bp'] - measured['uptime_bp'])} points; the pairwise loop "
        f"loses the trailing {window.seconds - measured['legacy_covered_s']} s of downtime and "
        f"reports {format_bp(measured['legacy_uptime_bp'])}% instead, and MTTR "
        f"{measured['mttr_s']} s and MTBF {measured['mtbf_s']} s come from the intervals rather "
        f"than from row counts; {passed}/{len(results)} checks pass."
    )
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
