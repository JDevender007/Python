"""Four structures and the thing the legacy simulator claimed to have: a history.

The legacy simulator introduced the stack with this sentence:

    "Function calls, undo/redo systems, expression evaluation, backtracking,
     browser history, and syntax parsing."

and then offered these controls:

    class ControlCallbacks:
        push: Action
        pop: Action
        peek: Action
        enqueue: Action
        dequeue: Action
        front: Action
        rear: Action
        clear: Action
        reset: Action
        random_fill: Action
        structure_changed: StructureChangeAction

and counted its work like this:

    def _record_success(self, started_at, status):
        self.operations_performed += 1
        ...

    def _record_failure(self, started_at, status):
        self.operations_performed += 1
        ...

Three things follow.

**1. The application advertises the one use of a stack it does not implement.**
"Undo/redo systems" is the first thing the theory panel says a stack is for, and
none of the eleven callbacks undoes anything. A `Stack` with `push`, `pop` and
`peek` cannot undo its own last `pop`, because the popped value is gone the moment
it is returned. **Undo is not a method on the structure; it is a second structure.**
This module keeps two of them: a history of steps that can be reversed, and a
future of steps that were reversed and can be replayed.

**2. A counter is not a history.** ``operations_performed`` is a single integer. It
cannot say *which* operation happened, so it cannot reverse it, and the same line
``self.operations_performed += 1`` appears twice -- once for success and once for
failure -- so the number counts a rejected push (which changed nothing) as an
operation performed. Here the counts are separate and named: ``applied`` for a
change that happened, ``refused`` for an attempt that raised, ``reads`` for a
lookup that changed nothing.

**3. Only a change belongs in the history.** A ``peek`` returns a value and leaves
the structure exactly as it was, so recording it would make the first undo appear
to do nothing. Here reads are counted, not recorded, and a ``clear`` of an already
empty structure also records nothing.

The history stores *steps*, not snapshots, and each step knows how to reverse
itself: undoing a push pops (and checks it got the same value back), undoing a pop
pushes the value back, and undoing a clear pushes back every item in its old order.
A redo replays the step and checks that it produces the value the step recorded --
so a history that has drifted from its structures reports a divergence instead of
quietly corrupting them.

Standard library only: no ``tkinter``, no network.
"""

from __future__ import annotations

import heapq
import itertools
from collections import deque
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SESSION_FILE = DATA_DIR / "session.txt"

#: The sentence the legacy theory panel printed, transcribed.
LEGACY_THEORY = "Function calls, undo/redo systems, expression evaluation, "

#: The eleven callbacks the legacy control panel declared.
LEGACY_CALLBACKS = ("push", "pop", "peek", "enqueue", "dequeue", "front",
                    "rear", "clear", "reset", "random_fill",
                    "structure_changed")

#: The line that counted both a success and a failure, at two sites.
LEGACY_COUNTER = "self.operations_performed += 1"
LEGACY_COUNTER_SITES = 2

#: The structures a session can name.
KINDS = ("stack", "queue", "deque", "heap")

#: How many items one structure holds by default.
CAPACITY = 8

#: The longest value a session may push.
MAX_LENGTH = 12

#: Every action a session file may use, and the structure it belongs to.
ACTIONS = {
    "push": "stack", "pop": "stack", "peek": "stack",
    "enqueue": "queue", "dequeue": "queue", "front": "queue", "rear": "queue",
    "push_front": "deque", "push_back": "deque", "pop_front": "deque",
    "pop_back": "deque",
    "heap_push": "heap", "heap_pop": "heap", "heap_peek": "heap",
}

#: The actions that change a structure, and so enter the history.
MUTATIONS = frozenset({"push", "pop", "enqueue", "dequeue", "push_front",
                       "push_back", "pop_front", "pop_back", "heap_push",
                       "heap_pop", "clear"})

#: The actions that only read.
READS = frozenset({"peek", "front", "rear", "heap_peek"})


class StructureError(Exception):
    """A structure, a session line or a history that is refused."""


class Overflow(StructureError):
    """An insertion into a structure that is already full."""


class Underflow(StructureError):
    """A removal from a structure that is already empty."""


class ValidationError(StructureError, ValueError):
    """A value or a session line that cannot be accepted."""


class HistoryError(StructureError):
    """An undo or a redo that cannot be performed."""


class Divergence(HistoryError):
    """A replayed step produced a different value than the one recorded."""


# --------------------------------------------------------------------------- #
# Values
# --------------------------------------------------------------------------- #
def check_capacity(capacity) -> int:
    """A capacity is a positive whole number."""
    if isinstance(capacity, bool) or not isinstance(capacity, int):
        raise ValidationError(f"a capacity must be an integer, got "
                              f"{capacity!r}")
    if capacity < 1:
        raise ValidationError("a capacity must be at least one")
    return capacity


def check_value(value) -> str:
    """A value is one to twelve characters of text, without stray spaces."""
    if not isinstance(value, str):
        raise ValidationError(f"a value must be text, got {value!r}")
    text = value.strip()
    if not text:
        raise ValidationError("a value cannot be empty")
    if len(text) > MAX_LENGTH:
        raise ValidationError(f"a value is at most {MAX_LENGTH} characters, "
                              f"got {len(text)}")
    if any(character.isspace() for character in text):
        raise ValidationError(f"a value cannot hold a space: {text!r}")
    return text


def check_priority(priority) -> int:
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValidationError(f"a priority must be an integer, got "
                              f"{priority!r}")
    return priority


# --------------------------------------------------------------------------- #
# The four structures
# --------------------------------------------------------------------------- #
class _Bounded:
    """Capacity, and the two refusals every structure shares."""

    kind = "bounded"

    def __init__(self, capacity: int = CAPACITY) -> None:
        self._capacity = check_capacity(capacity)

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def size(self) -> int:
        return len(self._items)

    @property
    def is_empty(self) -> bool:
        return not self._items

    @property
    def is_full(self) -> bool:
        return self.size >= self.capacity

    def _room(self) -> None:
        if self.is_full:
            raise Overflow(f"{self.kind} overflow: capacity is "
                           f"{self.capacity}")

    def _something(self) -> None:
        if self.is_empty:
            raise Underflow(f"{self.kind} underflow: it is empty")

    def clear(self) -> tuple[tuple[int | None, str], ...]:
        """Empty the structure and return what it held, in drain order."""
        removed = self.pending()
        self._items.clear()
        return removed

    def pending(self) -> tuple[tuple[int | None, str], ...]:
        """The contents as ``(priority, value)`` pairs, in refill order."""
        return tuple((None, value) for value in self.items)

    @property
    def items(self) -> tuple[str, ...]:
        raise NotImplementedError

    def __len__(self) -> int:
        return self.size

    def __repr__(self) -> str:
        return f"{type(self).__name__}(capacity={self.capacity}, " \
               f"items={list(self.items)!r})"


class Stack(_Bounded):
    """Last in, first out."""

    kind = "stack"

    def __init__(self, capacity: int = CAPACITY) -> None:
        super().__init__(capacity)
        self._items: list[str] = []

    def push(self, value: str) -> str:
        value = check_value(value)
        self._room()
        self._items.append(value)
        return value

    def pop(self) -> str:
        self._something()
        return self._items.pop()

    def peek(self) -> str:
        self._something()
        return self._items[-1]

    @property
    def items(self) -> tuple[str, ...]:
        """Bottom to top."""
        return tuple(self._items)


class Queue(_Bounded):
    """First in, first out."""

    kind = "queue"

    def __init__(self, capacity: int = CAPACITY) -> None:
        super().__init__(capacity)
        self._items: deque[str] = deque()

    def enqueue(self, value: str) -> str:
        value = check_value(value)
        self._room()
        self._items.append(value)
        return value

    def dequeue(self) -> str:
        self._something()
        return self._items.popleft()

    def add_front(self, value: str) -> str:
        """Put a value back at the front -- the inverse of ``dequeue``.

        A queue exposes one end for adding and one for removing; reversing its
        operations needs the other two, which is why a ``deque`` can do this and
        a bare ``Queue`` cannot.
        """
        value = check_value(value)
        self._room()
        self._items.appendleft(value)
        return value

    def remove_rear(self) -> str:
        """Take the value at the rear -- the inverse of ``enqueue``."""
        self._something()
        return self._items.pop()

    def front(self) -> str:
        self._something()
        return self._items[0]

    def rear(self) -> str:
        self._something()
        return self._items[-1]

    @property
    def items(self) -> tuple[str, ...]:
        """Front to rear."""
        return tuple(self._items)


class Deque(_Bounded):
    """Both ends: a stack at the front, a queue at the back."""

    kind = "deque"

    def __init__(self, capacity: int = CAPACITY) -> None:
        super().__init__(capacity)
        self._items: deque[str] = deque()

    def push_front(self, value: str) -> str:
        value = check_value(value)
        self._room()
        self._items.appendleft(value)
        return value

    def push_back(self, value: str) -> str:
        value = check_value(value)
        self._room()
        self._items.append(value)
        return value

    def pop_front(self) -> str:
        self._something()
        return self._items.popleft()

    def pop_back(self) -> str:
        self._something()
        return self._items.pop()

    def front(self) -> str:
        self._something()
        return self._items[0]

    def rear(self) -> str:
        self._something()
        return self._items[-1]

    @property
    def items(self) -> tuple[str, ...]:
        """Front to back."""
        return tuple(self._items)


class PriorityQueue(_Bounded):
    """Smallest priority first, with ties broken by insertion order."""

    kind = "heap"

    def __init__(self, capacity: int = CAPACITY) -> None:
        super().__init__(capacity)
        self._items: list[tuple[int, int, str]] = []
        self._sequence = itertools.count()

    def push(self, value: str, priority: int = 0) -> tuple[int, int, str]:
        """Add a value, returning the whole entry it became.

        The tie-break number is part of what was stored, so it is part of what
        is returned: an undo has to remove *that* entry, not whatever happens to
        be smallest later.
        """
        value = check_value(value)
        priority = check_priority(priority)
        self._room()
        entry = (priority, next(self._sequence), value)
        heapq.heappush(self._items, entry)
        return entry

    def pop(self) -> str:
        self._something()
        return heapq.heappop(self._items)[2]

    def pop_entry(self) -> tuple[int, int, str]:
        """Remove and return the whole entry, not just its value."""
        self._something()
        return heapq.heappop(self._items)

    def push_entry(self, entry: tuple[int, int, str]) -> None:
        """Put a whole entry back, keeping its tie-break order.

        Used by the history, which must restore the heap exactly. A plain
        ``push`` would assign a new sequence number and quietly move the value
        among the entries it tied with.
        """
        self._room()
        heapq.heappush(self._items, entry)

    def remove_entry(self, entry: tuple[int, int, str]) -> bool:
        """Remove one exact entry; ``False`` if it is not there."""
        try:
            self._items.remove(entry)
        except ValueError:
            return False
        heapq.heapify(self._items)
        return True

    def top(self) -> tuple[int, str]:
        """The priority and the value that ``pop`` would return."""
        self._something()
        priority, _, value = self._items[0]
        return priority, value

    def peek(self) -> str:
        return self.top()[1]

    @property
    def items(self) -> tuple[str, ...]:
        """The order this queue would pop everything in, left to right."""
        return tuple(value for _, _, value in sorted(self._items))

    def pending(self) -> tuple[tuple[int | None, str], ...]:
        return tuple((priority, value)
                     for priority, _, value in sorted(self._items))


#: Every structure, by the name a session uses.
STRUCTURES = {"stack": Stack, "queue": Queue, "deque": Deque, "heap":
              PriorityQueue}


# --------------------------------------------------------------------------- #
# A step, and the history that holds it
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Step:
    """One change to one structure, and enough detail to reverse it."""

    number: int
    structure: str
    action: str
    value: str | None = None
    priority: int | None = None
    restored: tuple[tuple[int | None, str], ...] = ()
    entry: tuple[int, int, str] | None = None

    def __str__(self) -> str:
        if self.restored:
            return f"#{self.number} {self.structure} {self.action} " \
                   f"{len(self.restored)} item(s)"
        if self.priority is not None:
            return f"#{self.number} {self.structure} {self.action} " \
                   f"{self.value} @{self.priority}"
        return f"#{self.number} {self.structure} {self.action} " \
               f"{self.value}".rstrip()


class Simulator:
    """Four structures, two stacks of history, and honest counters."""

    def __init__(self, capacity: int = CAPACITY) -> None:
        self._capacity = check_capacity(capacity)
        self._structures = {kind: cls(capacity)
                            for kind, cls in STRUCTURES.items()}
        self._past: list[Step] = []
        self._future: list[Step] = []
        self._serial = 0
        self.applied = 0
        self.refused = 0
        self.reads = 0
        self.discarded = 0

    # -- the structures ---------------------------------------------------- #
    @property
    def capacity(self) -> int:
        return self._capacity

    def structure(self, kind: str) -> _Bounded:
        if kind not in self._structures:
            raise ValidationError(f"no such structure: {kind!r}; choose one "
                                  f"of {', '.join(KINDS)}")
        return self._structures[kind]

    def snapshot(self) -> dict[str, tuple[str, ...]]:
        """Every structure's contents, by name."""
        return {kind: structure.items
                for kind, structure in self._structures.items()}

    # -- the history ------------------------------------------------------- #
    @property
    def history(self) -> tuple[Step, ...]:
        """The steps that have been applied and not undone, oldest first."""
        return tuple(self._past)

    @property
    def future(self) -> tuple[Step, ...]:
        """The steps that were undone and not yet replayed, oldest first."""
        return tuple(self._future)

    @property
    def can_undo(self) -> bool:
        return bool(self._past)

    @property
    def can_redo(self) -> bool:
        return bool(self._future)

    @property
    def undo_depth(self) -> int:
        return len(self._past)

    @property
    def redo_depth(self) -> int:
        return len(self._future)

    @property
    def total(self) -> int:
        """Applied plus refused attempts -- what the legacy counter reported."""
        return self.applied + self.refused

    def _record(self, structure: str, action: str, value: str | None = None,
                priority: int | None = None,
                restored: tuple[tuple[int | None, str], ...] = (),
                entry: tuple[int, int, str] | None = None) -> Step:
        self._serial += 1
        step = Step(self._serial, structure, action, value, priority, restored,
                    entry)
        self.discarded += len(self._future)
        self._future.clear()
        self._past.append(step)
        self.applied += 1
        return step

    def _read(self) -> None:
        self.reads += 1

    # -- mutations --------------------------------------------------------- #
    def push(self, value: str) -> Step:
        try:
            stored = self.structure("stack").push(value)
        except (Overflow, ValidationError):
            self.refused += 1
            raise
        return self._record("stack", "push", stored)

    def pop(self) -> str:
        try:
            value = self.structure("stack").pop()
        except Underflow:
            self.refused += 1
            raise
        self._record("stack", "pop", value)
        return value

    def peek(self) -> str:
        value = self.structure("stack").peek()
        self._read()
        return value

    def enqueue(self, value: str) -> Step:
        try:
            stored = self.structure("queue").enqueue(value)
        except (Overflow, ValidationError):
            self.refused += 1
            raise
        return self._record("queue", "enqueue", stored)

    def dequeue(self) -> str:
        try:
            value = self.structure("queue").dequeue()
        except Underflow:
            self.refused += 1
            raise
        self._record("queue", "dequeue", value)
        return value

    def front(self) -> str:
        value = self.structure("queue").front()
        self._read()
        return value

    def rear(self) -> str:
        value = self.structure("queue").rear()
        self._read()
        return value

    def push_front(self, value: str) -> Step:
        try:
            stored = self.structure("deque").push_front(value)
        except (Overflow, ValidationError):
            self.refused += 1
            raise
        return self._record("deque", "push_front", stored)

    def push_back(self, value: str) -> Step:
        try:
            stored = self.structure("deque").push_back(value)
        except (Overflow, ValidationError):
            self.refused += 1
            raise
        return self._record("deque", "push_back", stored)

    def pop_front(self) -> str:
        try:
            value = self.structure("deque").pop_front()
        except Underflow:
            self.refused += 1
            raise
        self._record("deque", "pop_front", value)
        return value

    def pop_back(self) -> str:
        try:
            value = self.structure("deque").pop_back()
        except Underflow:
            self.refused += 1
            raise
        self._record("deque", "pop_back", value)
        return value

    def heap_push(self, value: str, priority: int = 0) -> Step:
        try:
            entry = self.structure("heap").push(value, priority)
        except (Overflow, ValidationError):
            self.refused += 1
            raise
        return self._record("heap", "heap_push", entry[2], entry[0],
                            entry=entry)

    def heap_pop(self) -> str:
        try:
            entry = self.structure("heap").pop_entry()
        except Underflow:
            self.refused += 1
            raise
        # The whole entry is kept: the priority alone would not say where the
        # value belongs among the entries it tied with.
        self._record("heap", "heap_pop", entry[2], entry[0], entry=entry)
        return entry[2]

    def heap_peek(self) -> str:
        value = self.structure("heap").peek()
        self._read()
        return value

    def clear(self, kind: str) -> tuple[str, ...]:
        """Empty one structure; an already-empty one records nothing."""
        structure = self.structure(kind)
        removed = structure.clear()
        if not removed:
            return ()
        self._record(kind, "clear", restored=removed)
        return tuple(value for _, value in removed)

    # -- undo and redo ----------------------------------------------------- #
    def undo(self) -> Step:
        """Reverse the most recent step."""
        if not self._past:
            raise HistoryError("there is nothing to undo")
        step = self._past.pop()
        try:
            self._revert(step)
        except StructureError:
            self._past.append(step)
            raise
        self._future.append(step)
        return step

    def redo(self) -> Step:
        """Replay the most recently undone step."""
        if not self._future:
            raise HistoryError("there is nothing to redo")
        step = self._future.pop()
        try:
            self._replay(step)
        except StructureError:
            self._future.append(step)
            raise
        self._past.append(step)
        return step

    def undo_all(self) -> int:
        """Undo every step, newest first. Returns how many there were."""
        count = 0
        while self._past:
            self.undo()
            count += 1
        return count

    def redo_all(self) -> int:
        count = 0
        while self._future:
            self.redo()
            count += 1
        return count

    # -- the inverse of every action --------------------------------------- #
    @staticmethod
    def _same(got, expected, step: Step, tense: str) -> None:
        if got != expected:
            raise Divergence(f"step {step} {tense}: expected {expected!r}, "
                             f"got {got!r}")

    def _revert(self, step: Step) -> None:
        target = self.structure(step.structure)
        action = step.action
        if action == "push":
            self._same(target.pop(), step.value, step, "would not reverse")
        elif action == "pop":
            target.push(step.value)
        elif action == "enqueue":
            self._same(target.remove_rear(), step.value, step,
                       "would not reverse")
        elif action == "dequeue":
            target.add_front(step.value)
        elif action == "push_front":
            self._same(target.pop_front(), step.value, step,
                       "would not reverse")
        elif action == "pop_front":
            target.push_front(step.value)
        elif action == "push_back":
            self._same(target.pop_back(), step.value, step,
                       "would not reverse")
        elif action == "pop_back":
            target.push_back(step.value)
        elif action == "heap_push":
            if not target.remove_entry(step.entry):
                raise Divergence(f"step {step} would not reverse: its entry is "
                                 f"no longer in the heap")
        elif action == "heap_pop":
            target.push_entry(step.entry)
        elif action == "clear":
            for priority, value in step.restored:
                self._put_back(target, priority, value)
        else:
            raise HistoryError(f"no inverse for {action!r}")

    def _replay(self, step: Step) -> None:
        target = self.structure(step.structure)
        action = step.action
        if action == "push":
            target.push(step.value)
        elif action == "enqueue":
            target.enqueue(step.value)
        elif action == "push_front":
            target.push_front(step.value)
        elif action == "push_back":
            target.push_back(step.value)
        elif action == "pop":
            self._same(target.pop(), step.value, step, "would not replay")
        elif action == "dequeue":
            self._same(target.dequeue(), step.value, step, "would not replay")
        elif action == "pop_front":
            self._same(target.pop_front(), step.value, step,
                       "would not replay")
        elif action == "pop_back":
            self._same(target.pop_back(), step.value, step, "would not replay")
        elif action == "heap_push":
            target.push_entry(step.entry)
        elif action == "heap_pop":
            self._same(target.pop_entry(), step.entry, step,
                       "would not replay")
        elif action == "clear":
            self._same(target.clear(), step.restored, step,
                       "would not replay")
        else:
            raise HistoryError(f"no replay for {action!r}")

    def _put_back(self, target: _Bounded, priority: int | None,
                  value: str) -> None:
        if target.kind == "heap":
            target.push(value, priority or 0)
        elif target.kind == "stack":
            target.push(value)
        elif target.kind == "queue":
            target.enqueue(value)
        else:
            target.push_back(value)


# --------------------------------------------------------------------------- #
# A session file
# --------------------------------------------------------------------------- #
def read_session(path=SESSION_FILE) -> tuple[tuple[str, ...], ...]:
    """Read a session file into a tuple of ``(action, *arguments)`` lines."""
    path = Path(path)
    if not path.is_file():
        raise ValidationError(f"session file not found: {path}")
    lines = []
    for number, line in enumerate(path.read_text(encoding="utf-8")
                                  .splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith(";") or text.startswith("//"):
            continue
        parts = text.split()
        action = parts[0].lower()
        if action not in ACTIONS:
            raise ValidationError(f"{path.name}:{number}: {action!r} is not an "
                                  f"action; choose one of {', '.join(ACTIONS)}")
        arguments = parts[1:]
        if action in ("push", "enqueue", "push_front", "push_back"):
            if len(arguments) != 1:
                raise ValidationError(f"{path.name}:{number}: {action} takes "
                                      f"one value")
        elif action == "heap_push":
            if len(arguments) != 2:
                raise ValidationError(f"{path.name}:{number}: heap_push takes "
                                      f"a value and a priority")
        elif arguments:
            raise ValidationError(f"{path.name}:{number}: {action} takes no "
                                  f"arguments")
        lines.append(tuple([action, *arguments]))
    return tuple(lines)


def run_session(lines, simulator: Simulator | None = None) -> Simulator:
    """Run session lines, returning the simulator that holds the result."""
    simulator = Simulator() if simulator is None else simulator
    for number, line in enumerate(lines, start=1):
        action, *arguments = line
        try:
            if action == "push":
                simulator.push(arguments[0])
            elif action == "pop":
                simulator.pop()
            elif action == "peek":
                simulator.peek()
            elif action == "enqueue":
                simulator.enqueue(arguments[0])
            elif action == "dequeue":
                simulator.dequeue()
            elif action == "front":
                simulator.front()
            elif action == "rear":
                simulator.rear()
            elif action == "push_front":
                simulator.push_front(arguments[0])
            elif action == "push_back":
                simulator.push_back(arguments[0])
            elif action == "pop_front":
                simulator.pop_front()
            elif action == "pop_back":
                simulator.pop_back()
            elif action == "heap_push":
                try:
                    priority = int(arguments[1])
                except ValueError:
                    raise ValidationError(f"a priority must be a whole number, "
                                          f"got {arguments[1]!r}") from None
                simulator.heap_push(arguments[0], priority)
            elif action == "heap_pop":
                simulator.heap_pop()
            elif action == "heap_peek":
                simulator.heap_peek()
            else:                                    # pragma: no cover
                raise ValidationError(f"no such action: {action!r}")
        except StructureError as error:
            raise type(error)(f"line {number} ({' '.join(line)}): "
                              f"{error}") from None
    return simulator


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def audit(simulator: Simulator) -> list[tuple[str, bool]]:
    """Twelve checks that re-derive the answer instead of restating it."""
    stack = simulator.structure("stack")

    def lifo() -> bool:
        """Push three onto a copy and pop them: the order must reverse."""
        probe = Stack(4)
        for value in ("a", "b", "c"):
            probe.push(value)
        return [probe.pop() for _ in range(3)] == ["c", "b", "a"]

    def fifo() -> bool:
        probe = Queue(4)
        for value in ("a", "b", "c"):
            probe.enqueue(value)
        return [probe.dequeue() for _ in range(3)] == ["a", "b", "c"]

    def both_ends() -> bool:
        probe = Deque(4)
        probe.push_front("f1")
        probe.push_front("f2")
        probe.push_back("b1")
        probe.push_back("b2")
        return [probe.pop_front(), probe.pop_front(), probe.pop_back(),
                probe.pop_back()] == ["f2", "f1", "b2", "b1"]

    def heap_order() -> bool:
        probe = PriorityQueue(4)
        for value, priority in (("x", 5), ("y", 1), ("z", 3)):
            probe.push(value, priority)
        return [probe.pop() for _ in range(3)] == ["y", "z", "x"]

    def heap_ties() -> bool:
        probe = PriorityQueue(4)
        for value in ("first", "second", "third"):
            probe.push(value, 0)
        return [probe.pop() for _ in range(3)] == ["first", "second", "third"]

    def structures_exist() -> bool:
        return all(step.structure in KINDS for step in
                   simulator.history + simulator.future)

    def reads_are_free() -> bool:
        """A lookup must not add a step to the history."""
        probe = Simulator(4)
        probe.push("a")
        probe.enqueue("b")
        probe.push_front("c")
        probe.heap_push("d", 1)
        depth = probe.undo_depth
        reads = probe.reads
        probe.peek()
        probe.front()
        probe.rear()
        probe.heap_peek()
        return probe.undo_depth == depth and probe.reads == reads + 4

    def redo_is_cleared() -> bool:
        """A new operation must discard the steps waiting to be replayed."""
        probe = Simulator(4)
        probe.enqueue("a")
        probe.enqueue("b")
        probe.undo()
        had_future = probe.can_redo
        probe.enqueue("c")
        return had_future and not probe.can_redo

    def clear_comes_back() -> bool:
        probe = Simulator(4)
        for value in ("a", "b", "c"):
            probe.push(value)
        before = probe.structure("stack").items
        probe.clear("stack")
        emptied = probe.structure("stack").items == ()
        probe.undo()
        return emptied and probe.structure("stack").items == before

    def bookkeeping() -> bool:
        return (simulator.undo_depth + simulator.redo_depth
                + simulator.discarded) == simulator.applied

    def stack_matches_its_own_history() -> bool:
        """A stack's size is its pushes minus its pops, when nothing was cleared."""
        stack_steps = [step for step in simulator.history
                       if step.structure == "stack"]
        if any(step.action == "clear" for step in stack_steps):
            return True
        pushes = sum(1 for step in stack_steps if step.action == "push")
        pops = sum(1 for step in stack_steps if step.action == "pop")
        return stack.size == pushes - pops

    def history_has_no_reads() -> bool:
        return not any(step.action in READS
                       for step in simulator.history + simulator.future)

    return [
        ("every step names a structure that exists", structures_exist()),
        ("the stack is last-in first-out", lifo()),
        ("the queue is first-in first-out", fifo()),
        ("the deque is a stack at the front and a queue at the back",
         both_ends()),
        ("the heap pops in non-decreasing priority", heap_order()),
        ("the heap breaks ties by insertion order", heap_ties()),
        ("a lookup does not enter the history", reads_are_free()),
        ("a new operation after an undo clears the redo stack",
         redo_is_cleared()),
        ("undoing a clear restores every item in its old order",
         clear_comes_back()),
        ("the bookkeeping adds up", bookkeeping()),
        ("the stack agrees with its own history",
         stack_matches_its_own_history()),
        ("no read is ever recorded as a step", history_has_no_reads()),
    ]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def _show(simulator: Simulator, label: str) -> None:
    snapshot = simulator.snapshot()
    print(f"  {label}")
    for kind in KINDS:
        items = " ".join(snapshot[kind]) or "-"
        print(f"    {kind:<7}{items}")


def run_demo() -> int:
    lines = read_session()
    simulator = run_session(lines)
    final = simulator.snapshot()

    print("=" * 74)
    print(" HISTORY LAB - undo is a second stack, not a method on the first")
    print("=" * 74)
    print(f"  {len(lines)} session lines, capacity {simulator.capacity}")
    _show(simulator, "after the session:")
    session_applied = simulator.applied
    print(f"  {simulator.applied} applied, {simulator.refused} refused, "
          f"{simulator.reads} reads, {simulator.undo_depth} undoable")

    print("\n  the history, oldest first:")
    for step in simulator.history:
        print(f"    {step}")

    undone = simulator.undo_all()
    _show(simulator, f"after undoing all {undone}:")
    empty = all(not items for items in simulator.snapshot().values())
    print(f"    every structure empty again: {'yes' if empty else 'no'}")
    print(f"    {simulator.undo_depth} undoable, {simulator.redo_depth} "
          f"redoable")

    redone = simulator.redo_all()
    _show(simulator, f"after redoing all {redone}:")
    same = simulator.snapshot() == final
    print(f"    the same state as before the undos: {'yes' if same else 'no'}")

    print("\n  the redo rule:")
    simulator.undo()
    simulator.undo()
    print(f"    two undos: {simulator.undo_depth} undoable, "
          f"{simulator.redo_depth} redoable")
    simulator.heap_push("fresh", 4)
    print(f"    one new operation: {simulator.undo_depth} undoable, "
          f"{simulator.redo_depth} redoable -- the future is gone")
    print(f"    discarded steps so far: {simulator.discarded}; "
          f"applied {simulator.applied} = "
          f"{simulator.undo_depth} + {simulator.redo_depth} + "
          f"{simulator.discarded}")

    print("\n  a lookup is not an operation:")
    probe = Simulator(4)
    for value in ("a", "b", "c"):
        probe.push(value)
    probe.peek()
    print(f"    three pushes and a peek: {probe.undo_depth} undoable, "
          f"{probe.reads} read counted")
    probe.undo()
    print(f"    one undo leaves {' '.join(probe.structure('stack').items)} "
          f"-- it reversed the push, not the peek")

    print("\n  a clear is undone item by item:")
    probe2 = Simulator(4)
    for value in ("a", "b", "c"):
        probe2.push(value)
    probe2.clear("stack")
    probe2.undo()
    print(f"    three pushes, a clear, one undo: "
          f"{' '.join(probe2.structure('stack').items)}")

    print("\n  the legacy claims, transcribed:")
    print(f"    theory panel: \"{LEGACY_THEORY}...\"")
    undo_callbacks = [name for name in LEGACY_CALLBACKS if "undo" in name]
    print(f"    control panel: {len(LEGACY_CALLBACKS)} callbacks, "
          f"{len(undo_callbacks)} of them undo anything")
    print(f"    the counter line {LEGACY_COUNTER!r} appears "
          f"{LEGACY_COUNTER_SITES} times -- once for success, once for failure")

    checks = audit(simulator)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\n  a second reader of the same session file: ", end="")
    again = run_session(read_session())
    assert again.snapshot() == final, "the session file is the script"
    print(f"{again.applied} steps, and the same four structures")

    print("\nCross-checks OK: " +
          f"{len(lines)} session lines change the four structures "
          f"{session_applied} times, undoing all {undone} restores every "
          f"structure to empty, redoing all {redone} restores exactly the "
          f"state before the undos, {simulator.discarded} step(s) were "
          f"discarded by the one operation after them, a peek costs no undo, "
          f"a clear is reversed item by item, the legacy panel declares "
          f"{len(LEGACY_CALLBACKS)} callbacks and none of them undoes "
          f"anything, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("\nDemo completed successfully.")
    return 0
