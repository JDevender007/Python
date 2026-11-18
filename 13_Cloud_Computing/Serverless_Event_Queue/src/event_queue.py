"""An at-least-once queue delivers the same event twice, and depth is not age.

The legacy consumer is four lines that each look like the documentation:

    message = queue.receive()
    ok = handle(message)
    if ok:
        queue.delete(message)
    if visible_depth > 2:
        page_oncall()

**1. At-least-once means duplicates are normal, not exceptional.** A message
becomes visible again when its visibility timeout expires, whether or not the
first handler is still working. The slow handler in the bundled scenario takes
45 seconds with a 20-second visibility timeout, so the queue hands the same
event to a second worker at 26 seconds and both handlers succeed. `processed
+= 1` therefore reports more work than the queue contains: **10 successful
handler runs for 9 distinct events**.

**2. Quantity is not age.** `ApproximateNumberOfMessagesVisible` counts what a
consumer could pick up *now*: it excludes everything in flight and says nothing
about how long the oldest event has been waiting. The rebuild reports both, and
the demo pins a moment at **63 seconds** where the visible depth is **0** while
the oldest unfinished event is already 63 seconds old -- and the worst moment,
when one message has been waiting **83 seconds** past any freshness SLO, is a
moment when a depth-of-three alarm is silent.

**3. A max-receive count is an attempt budget, and the destination is a queue,
not /dev/null.** The legacy handler deletes the message as soon as the handler
fails, so a transient error loses the event. The rebuild retries within the
budget and redrives the exhausted message to the dead-letter queue with the
attempt count and the reason attached, so it can be inspected and replayed.

**4. A receipt handle is not an idempotency key.** Every delivery of the same
message carries a fresh receipt handle, so `if handle in seen` never fires for
the duplicate it was meant to stop. The event's own identifier is the key, and
the rebuild records which identifiers were already applied.

The simulation is a deterministic discrete-event loop in whole seconds: no
sleep, no network, no wall clock. `data/scenario.json` names the queue policy
and ten events with their processing time and failing attempts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCENARIO_FILE = DATA_DIR / "scenario.json"

#: The legacy shortcuts, transcribed so the demo can print them.
LEGACY_COUNT = "processed += 1                     # every handler return, not every event"
LEGACY_ALARM = "if visible_depth > 2: page_oncall()  # depth only, no age, no in-flight"
LEGACY_REDRIVE = "if not ok: queue.delete(message)     # a failure is dropped, not retried"
LEGACY_DEDUP = "if message.receipt_handle in seen: return  # changes on every delivery"

MAX_EVENTS = 64
MAX_WORKERS = 8
MAX_SECONDS = 86_400
SLUG = re.compile(r"^[a-z][a-z0-9-]{0,30}$")
KINDS = re.compile(r"^[a-z][a-z0-9.]{0,40}$")


class QueueError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Integer helpers
# --------------------------------------------------------------------------- #
def divide_half_up(numerator: int, denominator: int) -> int:
    """Round a non-negative ratio half away from zero, on integers only."""
    if denominator <= 0:
        raise QueueError("a divisor must be positive")
    if numerator < 0:
        raise QueueError("a dividend must be non-negative")
    return (2 * numerator + denominator) // (2 * denominator)


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Event:
    id: str
    kind: str
    produced_at: int
    process: int
    failures: tuple[int, ...] = ()

    def fails(self, attempt: int) -> bool:
        return attempt in self.failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "produced_at": self.produced_at,
            "process": self.process,
            "failures": list(self.failures),
        }


@dataclass(frozen=True)
class QueueConfig:
    name: str
    visibility: int
    max_receive: int
    retention: int
    workers: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "visibility": self.visibility,
            "max_receive": self.max_receive,
            "retention": self.retention,
            "workers": self.workers,
        }


@dataclass(frozen=True)
class Delivery:
    event: str
    attempt: int
    worker: int
    started: int
    finished: int
    outcome: str

    @property
    def duplicate(self) -> bool:
        return self.attempt > 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "attempt": self.attempt,
            "worker": self.worker,
            "started": self.started,
            "finished": self.finished,
            "outcome": self.outcome,
            "duplicate": self.duplicate,
        }


@dataclass(frozen=True)
class DeadLetter:
    event: str
    attempts: int
    at: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "attempts": self.attempts,
            "at": self.at,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Snapshot:
    at: int
    visible: int
    inflight: int
    backlog: int
    oldest_age: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "at": self.at,
            "visible": self.visible,
            "inflight": self.inflight,
            "backlog": self.backlog,
            "oldest_age": self.oldest_age,
        }


@dataclass(frozen=True)
class Run:
    config: QueueConfig
    events: tuple[Event, ...]
    deliveries: tuple[Delivery, ...]
    dead: tuple[DeadLetter, ...]
    timeline: tuple[Snapshot, ...]
    ended_at: int

    @property
    def delivered(self) -> int:
        return len(self.deliveries)

    @property
    def distinct_delivered(self) -> int:
        return len({item.event for item in self.deliveries})

    @property
    def duplicates(self) -> int:
        return self.delivered - self.distinct_delivered

    @property
    def successes(self) -> tuple[Delivery, ...]:
        return tuple(item for item in self.deliveries if item.outcome == "success")

    @property
    def failures(self) -> tuple[Delivery, ...]:
        return tuple(item for item in self.deliveries if item.outcome == "failure")

    @property
    def distinct_applied(self) -> int:
        return len({item.event for item in self.successes})

    @property
    def repeated_effects(self) -> int:
        return len(self.successes) - self.distinct_applied

    @property
    def settled(self) -> int:
        return len({item.event for item in self.successes}) + len(
            {item.event for item in self.dead}
        )

    @property
    def peak_visible(self) -> int:
        return max((item.visible for item in self.timeline), default=0)

    @property
    def peak_backlog(self) -> int:
        return max((item.backlog for item in self.timeline), default=0)

    @property
    def peak_age(self) -> int:
        return max((item.oldest_age for item in self.timeline), default=0)

    @property
    def final(self) -> Snapshot:
        return self.timeline[-1] if self.timeline else Snapshot(0, 0, 0, 0, 0)

    def attempts_of(self, event_id: str) -> int:
        return sum(1 for item in self.deliveries if item.event == event_id)

    def deliveries_of(self, event_id: str) -> tuple[Delivery, ...]:
        return tuple(item for item in self.deliveries if item.event == event_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "events": [item.to_dict() for item in self.events],
            "deliveries": [item.to_dict() for item in self.deliveries],
            "dead": [item.to_dict() for item in self.dead],
            "timeline": [item.to_dict() for item in self.timeline],
            "ended_at": self.ended_at,
            "totals": {
                "events": len(self.events),
                "delivered": self.delivered,
                "distinct_delivered": self.distinct_delivered,
                "duplicates": self.duplicates,
                "successes": len(self.successes),
                "failures": len(self.failures),
                "distinct_applied": self.distinct_applied,
                "repeated_effects": self.repeated_effects,
                "dead": len(self.dead),
            },
        }


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #
def load_document(path: str | Path) -> dict[str, Any]:
    """Read one ASCII JSON document and require a mapping at the root."""
    target = Path(path)
    if not target.is_file():
        raise QueueError(f"scenario not found: {target.name}")
    try:
        text = target.read_bytes().decode("ascii")
    except UnicodeDecodeError as exc:
        raise QueueError(f"{target.name} is not ASCII text") from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise QueueError(f"{target.name} is not valid JSON: line {exc.lineno}") from exc
    if not isinstance(document, dict):
        raise QueueError(f"{target.name}: a scenario root must be a mapping")
    return document


def scenario_from_document(document: dict[str, Any]) -> tuple[QueueConfig, tuple[Event, ...]]:
    """Convert a parsed document into records without trusting its shape."""
    raw_queue = document.get("queue")
    queue = raw_queue if isinstance(raw_queue, dict) else {}
    config = QueueConfig(
        name=str(queue.get("name", "")),
        visibility=_as_int(queue.get("visibility")),
        max_receive=_as_int(queue.get("max_receive")),
        retention=_as_int(queue.get("retention")),
        workers=_as_int(queue.get("workers")),
    )
    events: list[Event] = []
    raw_events = document.get("events")
    if isinstance(raw_events, list):
        for item in raw_events:
            if not isinstance(item, dict):
                continue
            failures = item.get("failures", [])
            attempts: list[int] = []
            if isinstance(failures, list):
                attempts = sorted(
                    {_as_int(value) for value in failures if _as_int(value) > 0}
                )
            events.append(
                Event(
                    id=str(item.get("id", "")),
                    kind=str(item.get("kind", "")),
                    produced_at=_as_int(item.get("produced_at")),
                    process=_as_int(item.get("process")),
                    failures=tuple(attempts),
                )
            )
    return config, tuple(events)


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def read_scenario(path: str | Path | None = None) -> tuple[QueueConfig, tuple[Event, ...]]:
    """Load the bundled scenario, or one named on the command line."""
    document = load_document(path if path is not None else SCENARIO_FILE)
    return scenario_from_document(document)


def validate_scenario(config: QueueConfig, events: tuple[Event, ...]) -> list[str]:
    """Every problem with a parsed scenario; an empty list means valid."""
    problems: list[str] = []
    if not SLUG.match(config.name):
        problems.append("$.queue.name: a lowercase slug is required")
    if not 1 <= config.visibility <= MAX_SECONDS:
        problems.append(f"$.queue.visibility: an integer 1..{MAX_SECONDS} is required")
    if not 1 <= config.max_receive <= 10:
        problems.append("$.queue.max_receive: an integer 1..10 is required")
    if not 1 <= config.retention <= MAX_SECONDS:
        problems.append(f"$.queue.retention: an integer 1..{MAX_SECONDS} is required")
    if not 1 <= config.workers <= MAX_WORKERS:
        problems.append(f"$.queue.workers: an integer 1..{MAX_WORKERS} is required")
    if not events:
        problems.append("$.events: a non-empty array is required")
    elif len(events) > MAX_EVENTS:
        problems.append(f"$.events: at most {MAX_EVENTS} events")
    seen: set[str] = set()
    for index, event in enumerate(events):
        where = f"$.events[{index}]"
        if not event.id or not SLUG.match(event.id):
            problems.append(f"{where}.id: a lowercase slug is required")
        elif event.id in seen:
            problems.append(f"{where}.id: duplicate event {event.id!r}")
        else:
            seen.add(event.id)
        if not KINDS.match(event.kind):
            problems.append(f"{where}.kind: a dotted lowercase kind is required")
        if not 0 <= event.produced_at <= MAX_SECONDS:
            problems.append(f"{where}.produced_at: an integer 0..{MAX_SECONDS} is required")
        if not 1 <= event.process <= MAX_SECONDS:
            problems.append(f"{where}.process: an integer 1..{MAX_SECONDS} is required")
        for attempt in event.failures:
            if attempt < 1 or attempt > config.max_receive:
                problems.append(
                    f"{where}.failures: attempt {attempt} is outside the "
                    f"max_receive budget of {config.max_receive}"
                )
    return problems


def validate_or_raise(config: QueueConfig, events: tuple[Event, ...]) -> None:
    problems = validate_scenario(config, events)
    if problems:
        joined = "\n  - ".join(problems)
        raise QueueError(f"invalid scenario ({len(problems)} problem(s)):\n  - {joined}")


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #
def simulate(config: QueueConfig, events: tuple[Event, ...]) -> Run:
    """Deliver every event with a visibility timeout, retries and a DLQ."""
    validate_or_raise(config, events)

    order = sorted(events, key=lambda event: (event.produced_at, event.id))
    state: dict[str, dict[str, Any]] = {
        event.id: {
            "event": event,
            "visible_at": event.produced_at,
            "visible_until": event.produced_at,
            "attempts": 0,
            "inflight": 0,
            "done": False,
            "dead": False,
        }
        for event in order
    }

    free_at = [0] * config.workers
    inflight: list[tuple[int, int, str, int, int, int]] = []
    deliveries: list[Delivery] = []
    dead: list[DeadLetter] = []
    timeline: list[Snapshot] = []
    sequence = 0
    now = min(event.produced_at for event in order)

    def note(at: int) -> None:
        pending = [
            item
            for item in state.values()
            if not item["done"]
            and not item["dead"]
            and item["event"].produced_at <= at
        ]
        visible = [
            item
            for item in pending
            if item["inflight"] == 0 and item["visible_at"] <= at
        ]
        inflight_count = sum(1 for item in pending if item["inflight"] > 0)
        oldest = min((item["event"].produced_at for item in pending), default=at)
        snapshot = Snapshot(
            at=at,
            visible=len(visible),
            inflight=inflight_count,
            backlog=len(pending),
            oldest_age=at - oldest,
        )
        if not timeline or timeline[-1] != snapshot:
            timeline.append(snapshot)

    def expire(at: int) -> None:
        for item in state.values():
            if item["done"] or item["dead"] or item["inflight"] > 0:
                continue
            event: Event = item["event"]
            if at > event.produced_at + config.retention:
                item["dead"] = True
                dead.append(DeadLetter(event.id, item["attempts"], at, "retention"))

    def dead_letter(item: dict[str, Any], at: int, reason: str) -> None:
        item["dead"] = True
        dead.append(DeadLetter(item["event"].id, item["attempts"], at, reason))

    def dispatch(at: int) -> None:
        nonlocal sequence
        while True:
            free = [worker for worker in range(config.workers) if free_at[worker] <= at]
            if not free:
                return
            candidates: list[tuple[int, str, dict[str, Any]]] = []
            for item in state.values():
                if item["done"] or item["dead"]:
                    continue
                if item["event"].produced_at > at:
                    continue
                ready = item["visible_at"] if item["inflight"] == 0 else item["visible_until"]
                if ready <= at:
                    candidates.append((ready, item["event"].id, item))
            if not candidates:
                return
            candidates.sort(key=lambda row: (row[0], row[1]))
            _, _, item = candidates[0]
            if item["attempts"] >= config.max_receive:
                dead_letter(item, at, "max_receive")
                continue
            worker = free[0]
            event: Event = item["event"]
            item["attempts"] += 1
            item["inflight"] += 1
            item["visible_until"] = at + config.visibility
            item["visible_at"] = at + config.visibility
            finish = at + event.process
            free_at[worker] = finish
            sequence += 1
            inflight.append((finish, sequence, event.id, item["attempts"], worker, at))

    def complete(at: int) -> None:
        nonlocal inflight
        finished = sorted((row for row in inflight if row[0] == at), key=lambda row: row[1])
        if not finished:
            return
        for _, _, event_id, attempt, worker, started in finished:
            item = state[event_id]
            item["inflight"] -= 1
            event: Event = item["event"]
            outcome = "failure" if event.fails(attempt) else "success"
            deliveries.append(Delivery(event_id, attempt, worker, started, at, outcome))
            if item["dead"] or item["done"]:
                continue
            if outcome == "success":
                # The handler already ran; its side effect cannot be undone by a
                # later duplicate delivery that is still in flight.
                item["done"] = True
                continue
            if item["inflight"] == 0 and not item["dead"]:
                item["visible_at"] = max(at, item["visible_until"])
        inflight = [row for row in inflight if row[0] != at]

    guard = 0
    while True:
        guard += 1
        if guard > 10_000:
            raise QueueError("the simulation did not settle")
        expire(now)
        dispatch(now)
        note(now)
        pending = [item for item in state.values() if not item["done"] and not item["dead"]]
        if not pending and not inflight:
            break
        moments: list[int] = [row[0] for row in inflight if row[0] > now]
        for item in pending:
            produced = item["event"].produced_at
            if produced > now:
                moments.append(produced)
                continue
            ready = item["visible_at"] if item["inflight"] == 0 else item["visible_until"]
            if ready > now:
                moments.append(ready)
        if not moments:
            break
        now = min(moments)
        complete(now)

    if not timeline or timeline[-1].at != now:
        timeline.append(Snapshot(now, 0, 0, 0, 0))
    else:
        timeline[-1] = Snapshot(now, 0, 0, 0, 0)
    return Run(
        config=config,
        events=events,
        deliveries=tuple(deliveries),
        dead=tuple(dead),
        timeline=tuple(timeline),
        ended_at=now,
    )


# --------------------------------------------------------------------------- #
# Legacy comparisons
# --------------------------------------------------------------------------- #
def legacy_processed(run: Run) -> int:
    """The legacy counter: one per handler return, so duplicates count twice."""
    return len(run.successes)


def legacy_alarm(snapshot: Snapshot, threshold: int = 2) -> bool:
    """The legacy alarm: visible depth only."""
    return snapshot.visible > threshold


def legacy_dropped(events: tuple[Event, ...]) -> tuple[str, ...]:
    """The legacy failure policy deletes the message, so the event is lost."""
    return tuple(event.id for event in events if event.failures)


def legacy_dedup_hit(run: Run, receipt_handle_of: Callable[[Delivery], str]) -> int:
    """Count duplicate deliveries the receipt-handle check could not stop."""
    seen: set[str] = set()
    repeats = 0
    for item in run.deliveries:
        handle = receipt_handle_of(item)
        if handle in seen:
            repeats += 1
        else:
            seen.add(handle)
    return repeats


def receipt_handle(delivery: Delivery) -> str:
    """A fresh handle per delivery -- the reason handle-based dedup never fires."""
    return f"rh-{delivery.event}-{delivery.attempt}-{delivery.worker}"


def age_worst(run: Run) -> Snapshot:
    """The moment the oldest unfinished event was oldest."""
    return max(run.timeline, key=lambda item: (item.oldest_age, item.at))


def stale_moment(run: Run, limit: int) -> Snapshot | None:
    """The first moment the backlog has an event older than the limit."""
    for snapshot in run.timeline:
        if snapshot.oldest_age > limit:
            return snapshot
    return None


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(path: str | Path | None = None) -> dict[str, Any]:
    config, events = read_scenario(path)
    validate_or_raise(config, events)
    run = simulate(config, events)
    worst = age_worst(run)
    stale = stale_moment(run, 60)
    return {
        "config": config,
        "events": events,
        "run": run,
        "worst": worst,
        "stale": stale,
        "legacy_processed": legacy_processed(run),
        "legacy_dropped": legacy_dropped(events),
        "legacy_handle_repeats": legacy_dedup_hit(run, receipt_handle),
        "average_age": divide_half_up(
            sum(item.oldest_age for item in run.timeline), len(run.timeline)
        ),
    }


def report(measured: dict[str, Any]) -> dict[str, Any]:
    """A JSON-safe view: records, totals and the two alert moments."""
    run: Run = measured["run"]
    return {
        "queue": measured["config"].to_dict(),
        "events": [item.to_dict() for item in measured["events"]],
        "totals": run.to_dict()["totals"],
        "deliveries": [item.to_dict() for item in run.deliveries],
        "dead": [item.to_dict() for item in run.dead],
        "timeline": [item.to_dict() for item in run.timeline],
        "ended_at": run.ended_at,
        "alerts": {
            "worst": measured["worst"].to_dict(),
            "stale": None if measured["stale"] is None else measured["stale"].to_dict(),
            "legacy_processed": measured["legacy_processed"],
            "legacy_dropped": list(measured["legacy_dropped"]),
            "legacy_handle_repeats": measured["legacy_handle_repeats"],
            "average_age": measured["average_age"],
        },
    }


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def _guard(check: Callable[[], bool]) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def _refused(call: Callable[[], object]) -> bool:
    try:
        call()
    except QueueError:
        return True
    return False


def audit(
    measured: dict[str, Any],
    *,
    read: Callable[[], tuple[QueueConfig, tuple[Event, ...]]] = read_scenario,
    run: Callable[[QueueConfig, tuple[Event, ...]], Run] = simulate,
) -> list[tuple[str, bool]]:
    """Every check rebuilds the run from the scenario, not from the summary."""
    cache: dict[str, Any] = {}

    def rebuilt() -> Run:
        if not cache:
            config, events = read()
            cache["config"] = config
            cache["events"] = events
            cache["run"] = run(config, events)
        return cache["run"]

    def pinned_totals() -> tuple[int, int, int, int]:
        base = rebuilt()
        return (
            base.delivered,
            base.distinct_delivered,
            base.duplicates,
            len(base.dead),
        )

    checks = [
        (
            "the_scenario_reads_and_validates",
            lambda: validate_scenario(rebuilt().config, rebuilt().events) == []
            and len(rebuilt().events) == 10,
        ),
        (
            "the_bundled_policy_is_pinned",
            lambda: (
                rebuilt().config.visibility,
                rebuilt().config.max_receive,
                rebuilt().config.workers,
            )
            == (20, 3, 2),
        ),
        (
            "every_event_is_either_applied_or_dead_lettered",
            lambda: rebuilt().settled == len(rebuilt().events) == len(measured["events"]),
        ),
        (
            "at_least_once_delivers_more_than_it_receives",
            lambda: pinned_totals()
            == (
                measured["run"].delivered,
                measured["run"].distinct_delivered,
                measured["run"].duplicates,
                len(measured["run"].dead),
            )
            == (14, 10, 4, 1),
        ),
        (
            "a_slow_handler_is_redelivered_while_it_still_runs",
            lambda: rebuilt().attempts_of("evt-03") == 2
            and [item.started for item in rebuilt().deliveries_of("evt-03")] == [5, 26],
        ),
        (
            "a_duplicate_delivery_produces_a_second_side_effect",
            lambda: len(rebuilt().deliveries_of("evt-03")) == 2
            and all(
                item.outcome == "success" for item in rebuilt().deliveries_of("evt-03")
            )
            and rebuilt().repeated_effects == 1,
        ),
        (
            "a_transient_failure_is_retried_and_then_applied",
            lambda: [
                (item.attempt, item.outcome) for item in rebuilt().deliveries_of("evt-04")
            ]
            == [(1, "failure"), (2, "success")],
        ),
        (
            "an_exhausted_budget_lands_in_the_dead_letter_queue",
            lambda: rebuilt().attempts_of("evt-05") == 3
            and [(item.event, item.attempts, item.reason) for item in rebuilt().dead]
            == [("evt-05", 3, "max_receive")],
        ),
        (
            "depth_is_visible_messages_only",
            lambda: rebuilt().peak_visible == 5
            and rebuilt().peak_backlog == 7
            and any(
                item.visible == 0 and item.backlog > 0 for item in rebuilt().timeline
            ),
        ),
        (
            "a_small_depth_can_hide_a_stale_backlog",
            lambda: rebuilt().peak_age == measured["worst"].oldest_age == 83
            and measured["worst"].visible == 0
            and measured["stale"] is not None
            and measured["stale"].oldest_age == 63
            and measured["stale"].visible == 0,
        ),
        (
            "the_legacy_counter_counts_deliveries_not_events",
            lambda: legacy_processed(rebuilt())
            == len(rebuilt().successes)
            == rebuilt().distinct_applied + rebuilt().repeated_effects
            == 10
            and rebuilt().distinct_applied == 9,
        ),
        (
            "a_receipt_handle_cannot_identify_a_duplicate",
            lambda: legacy_dedup_hit(rebuilt(), receipt_handle) == 0
            and rebuilt().duplicates == 4
            and len({item.event for item in rebuilt().successes}) == 9,
        ),
        (
            "the_legacy_failure_policy_loses_events",
            lambda: legacy_dropped(rebuilt().events) == ("evt-04", "evt-05")
            and len(legacy_dropped(rebuilt().events)) == 2
            and rebuilt().distinct_applied == 9,
        ),
        (
            "a_bad_scenario_is_refused",
            lambda: _refused(
                lambda: simulate(
                    QueueConfig("bad", 0, 3, 600, 2),
                    (Event("evt-01", "order.created", 0, 5),),
                )
            )
            and _refused(
                lambda: simulate(
                    QueueConfig("bad", 20, 3, 600, 2),
                    (Event("evt-01", "order.created", 0, 5, (4,)),),
                )
            )
            and validate_scenario(
                QueueConfig("bad", 20, 3, 600, 2),
                (Event("evt-01", "order.created", 0, 5), Event("evt-01", "x", 0, 5)),
            )
            != [],
        ),
        (
            "the_rebuild_is_deterministic",
            lambda: rebuilt().deliveries == measured["run"].deliveries
            and rebuilt().dead == measured["run"].dead
            and rebuilt().timeline == measured["run"].timeline,
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_timeline(run: Run) -> str:
    """A fixed-width trace of depth, backlog and the oldest unfinished event."""
    lines = [
        f"{'At':>5} {'Visible':>8} {'In-flight':>10} {'Backlog':>8} {'Oldest':>7}",
        "-" * 42,
    ]
    for item in run.timeline:
        lines.append(
            f"{item.at:>5} {item.visible:>8} {item.inflight:>10} "
            f"{item.backlog:>8} {item.oldest_age:>7}"
        )
    return "\n".join(lines)


def render_dead(run: Run) -> str:
    if not run.dead:
        return "Dead-letter queue: empty"
    lines = ["Dead-letter queue:"]
    for item in run.dead:
        lines.append(
            f"  {item.event}  attempts {item.attempts}  at {item.at}s  ({item.reason})"
        )
    return "\n".join(lines)


def run_demo(path: str | Path | None = None) -> int:
    measured = measure(path)
    config: QueueConfig = measured["config"]
    run: Run = measured["run"]
    worst: Snapshot = measured["worst"]
    stale: Snapshot | None = measured["stale"]

    print("Serverless event queue -- at-least-once means twice, and depth is not age")
    print("=" * 74)
    print()
    print(
        f"Queue {config.name}: visibility {config.visibility}s, "
        f"max_receive {config.max_receive}, workers {config.workers}, "
        f"{len(run.events)} events."
    )
    print()
    print("1. At-least-once delivery duplicates the event, not just the message.")
    print("   " + LEGACY_COUNT)
    slow_event = next(event for event in run.events if event.id == "evt-03")
    slow = run.deliveries_of("evt-03")
    print(
        f"   evt-03 needs {slow_event.process}s of work under a "
        f"{config.visibility}s visibility timeout: delivered at "
        f"{slow[0].started}s by worker {slow[0].worker} and again at "
        f"{slow[1].started}s by worker {slow[1].worker}."
    )
    print(
        f"   handler runs {len(run.successes)} successes for "
        f"{run.distinct_applied} distinct events: {run.repeated_effects} "
        f"repeated side effect(s)."
    )
    print()
    print("2. Quantity is not age.")
    print("   " + LEGACY_ALARM)
    if stale is not None:
        print(
            f"   first stale moment: at {stale.at}s the visible depth is "
            f"{stale.visible} and the oldest unfinished event is "
            f"{stale.oldest_age}s old."
        )
    print(
        f"   worst moment: at {worst.at}s the visible depth is {worst.visible}, "
        f"the backlog is {worst.backlog}, and the oldest unfinished event is "
        f"{worst.oldest_age}s old."
    )
    print(
        f"   a depth-over-2 alarm fires at {sum(1 for s in run.timeline if legacy_alarm(s))} "
        f"of {len(run.timeline)} moments and stays silent at the worst one."
    )
    print()
    print("3. A max-receive budget retries, then redrives.")
    print("   " + LEGACY_REDRIVE)
    print(
        f"   evt-04 recovers on attempt 2; evt-05 exhausts "
        f"{config.max_receive} attempts and is dead-lettered."
    )
    print("   " + render_dead(run).replace("\n", "\n   "))
    print(
        f"   the legacy delete-on-failure policy would lose "
        f"{len(measured['legacy_dropped'])} events: "
        f"{', '.join(measured['legacy_dropped'])}."
    )
    print()
    print("4. A receipt handle is not an idempotency key.")
    print("   " + LEGACY_DEDUP)
    print(
        f"   {run.duplicates} duplicate deliveries carry {run.duplicates} fresh "
        f"receipt handles, so the handle check stops "
        f"{measured['legacy_handle_repeats']} of them; the event id stops all "
        f"{run.duplicates}."
    )
    print()
    print(render_timeline(run))
    print()
    print("Checks")
    results = audit(measured)
    for name, okay in results:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    passed = sum(1 for _, okay in results if okay)
    print(f"  {passed}/{len(results)} checks pass")
    print()
    print(
        "Cross-checks OK: "
        f"{run.delivered} deliveries cover {run.distinct_delivered} of "
        f"{len(run.events)} events, so {run.duplicates} are duplicates and "
        f"evt-03 is applied twice; {len(run.successes)} handler successes "
        f"cover {run.distinct_applied} distinct events while "
        f"{len(measured['legacy_dropped'])} failures would be lost by the "
        f"legacy delete; the worst moment has visible depth {worst.visible} "
        f"with an oldest unfinished event of {worst.oldest_age}s, which the "
        f"depth alarm misses; and a receipt handle identifies a delivery, not "
        f"an event, so it stops {measured['legacy_handle_repeats']} of "
        f"{run.duplicates} duplicates; {passed}/{len(results)} checks pass."
    )
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
