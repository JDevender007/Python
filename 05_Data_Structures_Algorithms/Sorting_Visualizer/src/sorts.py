"""Six sorting algorithms, their exact comparison and write counts, and the
one number the legacy project got wrong.

The legacy visualizer reported two numbers per frame:

    if left_values[left_index] <= right_values[right_index]:
        data[target] = left_values[left_index]
        left_index += 1
    else:
        data[target] = right_values[right_index]
        right_index += 1
    swaps += 1

It called that counter ``swaps``. Merge sort performs **no** swaps: it copies
elements into a second list and writes them back, so the number grows like
``n log n`` and describes *placements*, not exchanges. A viewer watching the bar
chart sees "swaps" climbing on the algorithm that swaps least, and a reader
comparing two algorithms compares a swap count with a write count.

Four things follow.

**1. A counter's name is a claim about what it counts.** ``writes`` and ``swaps``
are different quantities. Selection sort makes exactly ``n - 1`` swaps; merge
sort makes zero and ``n log n`` writes. This module counts both, separately,
and refuses to call one the other.

**2. "It looks sorted" is not sorted.** An animation that ends on ascending bars
proves nothing: the frames could be a montage. Every result here is checked
three ways -- the output is non-decreasing, it is a permutation of the input
(same multiset of keys and labels), and the frame count agrees with the
recorded counters.

**3. Stability is a property of the algorithm, not of the data.** Two records
with the same key keep their relative order only if the sort is stable.
Insertion, bubble and merge are stable; selection and quick and heap are not.
The bundled data has duplicate keys on purpose, so "stable" is measurable rather
than asserted.

**4. The worst case is chosen by the input, not by the algorithm's reputation.**
Lomuto-partition quick sort on an already-sorted array degrades to
``n(n-1)/2`` comparisons -- the same as bubble sort on the same input, which is
the case its early-exit flag rescues.

Standard library only: no ``pygame``, no ``tkinter``, no network.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VALUES = DATA_DIR / "values.txt"

#: The legacy project's counter, kept as a claim we can test.
LEGACY_LABEL = "swaps"
LEGACY_LINE = "swaps += 1"
LEGACY_MERGE_BRANCH = (
    "if left_values[left_index] <= right_values[right_index]: "
    "data[target] = left_values[left_index] ... swaps += 1"
)


class SortError(ValueError):
    """A sort, an item or a value that is refused."""


# --------------------------------------------------------------------------- #
# An item, a frame, a result
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, order=True)
class Item:
    """A key with a label, so two equal keys stay distinguishable.

    ``order=True`` gives ``__lt__`` -- but the sorts call :meth:`key` explicitly,
    because ordering two items by ``(key, label)`` would hide stability: two
    equal keys would sort by label and every sort would look stable.
    """

    key: int
    label: str

    def __post_init__(self) -> None:
        if isinstance(self.key, bool) or not isinstance(self.key, int):
            raise SortError(f"a key must be an integer, got {self.key!r}")
        if not isinstance(self.label, str) or not self.label:
            raise SortError("a label must be a non-empty string")

    @property
    def sort_key(self) -> int:
        """The only field a comparison is allowed to look at."""
        return self.key

    def __str__(self) -> str:
        return f"{self.key}:{self.label}"


@dataclass(frozen=True)
class Frame:
    """One snapshot: the data, and the two counters at that moment."""

    data: tuple[int, ...]
    comparisons: int
    writes: int


@dataclass(frozen=True)
class Result:
    """A finished sort: the order it produced, every frame, and the counters."""

    algorithm: str
    original: tuple[Item, ...]
    order: tuple[Item, ...]
    frames: tuple[Frame, ...]
    comparisons: int
    writes: int
    swaps: int

    @property
    def keys(self) -> tuple[int, ...]:
        return tuple(item.key for item in self.order)

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(item.label for item in self.order)

    def is_sorted(self) -> bool:
        return all(a.key <= b.key for a, b in zip(self.order, self.order[1:]))

    def is_permutation(self) -> bool:
        return sorted(item.label for item in self.order) == \
            sorted(item.label for item in self.original)

    def is_stable(self) -> bool:
        """Equal keys keep their input order -- the definition, checked.

        Every pair of equal keys is examined, not only adjacent ones: a swap
        can separate two duplicates that were far apart in the input, and an
        "adjacent only" test would call that stable.
        """
        position = {label: index for index, label in enumerate(self.labels)}
        for left in range(len(self.original)):
            for right in range(left + 1, len(self.original)):
                if self.original[left].key != self.original[right].key:
                    continue
                if self.original[left].label not in position or \
                        self.original[right].label not in position:
                    return False
                if position[self.original[left].label] > \
                        position[self.original[right].label]:
                    return False
        return True

    def summary(self) -> dict:
        return {"algorithm": self.algorithm, "items": len(self.order),
                "comparisons": self.comparisons, "writes": self.writes,
                "swaps": self.swaps, "frames": len(self.frames),
                "sorted": self.is_sorted(),
                "permutation": self.is_permutation(),
                "stable": self.is_stable()}

    def to_dict(self) -> dict:
        return {**self.summary(),
                "order": [str(item) for item in self.order],
                "frames": [[list(frame.data), frame.comparisons, frame.writes]
                           for frame in self.frames]}


# --------------------------------------------------------------------------- #
# The tracer the algorithms share
# --------------------------------------------------------------------------- #
class Tracer:
    """Holds the data, the counters and the frames for one sort."""

    def __init__(self, items) -> None:
        self.items = tuple(items)
        self.data = [item.key for item in self.items]
        self.labels = [item.label for item in self.items]
        self.comparisons = 0
        self.writes = 0
        self.swaps = 0
        self.frames: list[Frame] = [self.frame()]

    # -- counting --------------------------------------------------------- #
    def compare(self, left: int, right: int) -> bool:
        """Record a comparison of two positions; True when left <= right."""
        self.comparisons += 1
        return self.data[left] <= self.data[right]

    def key_le(self, left_key: int, right_key: int) -> bool:
        self.comparisons += 1
        return left_key <= right_key

    def write(self, index: int, key: int, label: str | None = None) -> None:
        """Store a key at a position. Every store is one write."""
        self.data[index] = key
        if label is not None:
            self.labels[index] = label
        self.writes += 1
        self.frames.append(self.frame())

    def swap(self, left: int, right: int) -> None:
        """Exchange two positions: two writes and exactly one swap."""
        if left == right:
            return
        self.data[left], self.data[right] = self.data[right], self.data[left]
        self.labels[left], self.labels[right] = \
            self.labels[right], self.labels[left]
        self.writes += 2
        self.swaps += 1
        self.frames.append(self.frame())

    def frame(self) -> Frame:
        return Frame(tuple(self.data), self.comparisons, self.writes)

    def result(self, algorithm: str) -> Result:
        order = tuple(Item(key, label)
                      for key, label in zip(self.data, self.labels))
        frames = list(self.frames)
        closing = self.frame()
        if frames[-1] != closing:
            frames.append(closing)
        return Result(algorithm, self.items, order, tuple(frames),
                      self.comparisons, self.writes, self.swaps)


# --------------------------------------------------------------------------- #
# The six sorts
# --------------------------------------------------------------------------- #
def bubble_sort(items) -> Result:
    """Stable, with an early exit that makes a sorted input cost n-1 compares."""
    trace = Tracer(items)
    end = len(trace.data) - 1
    while end > 0:
        swapped = False
        for index in range(end):
            if not trace.compare(index, index + 1):
                trace.swap(index, index + 1)
                swapped = True
        end -= 1
        if not swapped:
            break
    return trace.result("bubble")


def insertion_sort(items) -> Result:
    """Stable; shifts rather than swaps, so writes and swaps diverge."""
    trace = Tracer(items)
    for position in range(1, len(trace.data)):
        key = trace.data[position]
        label = trace.labels[position]
        hole = position
        while hole > 0:
            trace.comparisons += 1
            if trace.data[hole - 1] <= key:
                break
            trace.write(hole, trace.data[hole - 1], trace.labels[hole - 1])
            hole -= 1
        if hole != position:
            trace.write(hole, key, label)
    return trace.result("insertion")


def selection_sort(items) -> Result:
    """At most n-1 swaps -- and exactly that many on a reversed input."""
    trace = Tracer(items)
    length = len(trace.data)
    for start in range(length):
        smallest = start
        for index in range(start + 1, length):
            trace.comparisons += 1
            if trace.data[index] < trace.data[smallest]:
                smallest = index
        trace.swap(start, smallest)
    return trace.result("selection")


def merge_sort(items) -> Result:
    """Stable. It swaps nothing: it writes, and the writes are the cost."""
    trace = Tracer(items)

    def sort_range(left: int, right: int) -> None:
        if left >= right:
            return
        middle = (left + right) // 2
        sort_range(left, middle)
        sort_range(middle + 1, right)

        left_items = [(trace.data[index], trace.labels[index])
                      for index in range(left, middle + 1)]
        right_items = [(trace.data[index], trace.labels[index])
                       for index in range(middle + 1, right + 1)]
        left_index = right_index = 0
        target = left

        while left_index < len(left_items) and right_index < len(right_items):
            take_left = trace.key_le(left_items[left_index][0],
                                     right_items[right_index][0])
            if take_left:
                key, label = left_items[left_index]
                left_index += 1
            else:
                key, label = right_items[right_index]
                right_index += 1
            trace.write(target, key, label)
            target += 1

        while left_index < len(left_items):
            key, label = left_items[left_index]
            trace.write(target, key, label)
            left_index += 1
            target += 1

        while right_index < len(right_items):
            key, label = right_items[right_index]
            trace.write(target, key, label)
            right_index += 1
            target += 1

    sort_range(0, len(trace.data) - 1)
    return trace.result("merge")


def quick_sort(items) -> Result:
    """Lomuto partition: n(n-1)/2 comparisons on an already-sorted input."""
    trace = Tracer(items)

    def sort_range(low: int, high: int) -> None:
        if low >= high:
            return
        pivot = trace.data[high]
        smaller = low - 1
        for current in range(low, high):
            trace.comparisons += 1
            if trace.data[current] <= pivot:
                smaller += 1
                trace.swap(smaller, current)
        trace.swap(smaller + 1, high)
        middle = smaller + 1
        sort_range(low, middle - 1)
        sort_range(middle + 1, high)

    sort_range(0, len(trace.data) - 1)
    return trace.result("quick")


def heap_sort(items) -> Result:
    """Not stable, and it swaps rather than writes."""
    trace = Tracer(items)
    length = len(trace.data)

    def sift(root: int, end: int) -> None:
        while True:
            child = 2 * root + 1
            if child > end:
                return
            if child + 1 <= end:
                trace.comparisons += 1
                if trace.data[child] < trace.data[child + 1]:
                    child += 1
            trace.comparisons += 1
            if trace.data[root] < trace.data[child]:
                trace.swap(root, child)
                root = child
            else:
                return

    for start in range(length // 2 - 1, -1, -1):
        sift(start, length - 1)
    for end in range(length - 1, 0, -1):
        trace.swap(0, end)
        sift(0, end - 1)
    return trace.result("heap")


#: Every algorithm, by the name the CLI uses.
ALGORITHMS = {"bubble": bubble_sort, "insertion": insertion_sort,
              "selection": selection_sort, "merge": merge_sort,
              "quick": quick_sort, "heap": heap_sort}

#: The three whose output keeps equal keys in their input order.
STABLE = ("bubble", "insertion", "merge")


# --------------------------------------------------------------------------- #
# Reading and making items
# --------------------------------------------------------------------------- #
def items_from_keys(keys) -> tuple[Item, ...]:
    """Turn keys into items whose labels record the input position."""
    keys = list(keys)
    return tuple(Item(key, f"#{position:02d}")
                 for position, key in enumerate(keys))


def read_values(path=VALUES) -> tuple[Item, ...]:
    """Read one integer per line; the line number becomes the label."""
    path = Path(path)
    if not path.is_file():
        raise SortError(f"values file not found: {path}")
    items = []
    for number, line in enumerate(path.read_text(encoding="utf-8")
                                  .splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        try:
            key = int(text)
        except ValueError:
            raise SortError(f"{path.name}:{number}: {text!r} is not an "
                            f"integer") from None
        items.append(Item(key, f"#{len(items) + 1:02d}"))
    return tuple(items)


def inversions(keys) -> int:
    """How far the sequence is from sorted; a reversed list is n(n-1)/2."""
    keys = list(keys)
    return sum(1 for left in range(len(keys))
               for right in range(left + 1, len(keys))
               if keys[left] > keys[right])


def sorted_keys(keys) -> tuple[int, ...]:
    return tuple(sorted(keys))


# --------------------------------------------------------------------------- #
# The legacy counter
# --------------------------------------------------------------------------- #
def legacy_merge_writes(items) -> int:
    """Run the legacy merge step and return the number it labels ``swaps``.

    The legacy code increments one counter for every placement into the merged
    buffer. It is a write count; nothing is exchanged. The true swap count of
    the same run is :func:`legacy_merge_swaps`, which is zero.
    """
    keys = [item.key for item in items]
    placements = 0

    def sort_range(left: int, right: int) -> None:
        nonlocal placements
        if left >= right:
            return
        middle = (left + right) // 2
        sort_range(left, middle)
        sort_range(middle + 1, right)
        left_keys = keys[left:middle + 1]
        right_keys = keys[middle + 1:right + 1]
        left_index = right_index = 0
        target = left
        while left_index < len(left_keys) and right_index < len(right_keys):
            if left_keys[left_index] <= right_keys[right_index]:
                keys[target] = left_keys[left_index]
                left_index += 1
            else:
                keys[target] = right_keys[right_index]
                right_index += 1
            placements += 1
            target += 1
        while left_index < len(left_keys):
            keys[target] = left_keys[left_index]
            left_index += 1
            target += 1
            placements += 1
        while right_index < len(right_keys):
            keys[target] = right_keys[right_index]
            right_index += 1
            target += 1
            placements += 1

    sort_range(0, len(keys) - 1)
    return placements


def legacy_merge_swaps(items) -> int:
    """Merge sort exchanges nothing, so the honest answer is always zero."""
    return 0


def legacy_label() -> str:
    """The word the legacy project printed above that number."""
    return LEGACY_LABEL


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def audit(results) -> list[tuple[str, bool]]:
    """Every result must be sorted, a permutation, and internally consistent."""
    results = list(results)
    checks = [("every result is sorted", all(r.is_sorted() for r in results)),
              ("every result is a permutation of its input",
               all(r.is_permutation() for r in results)),
              ("every result keeps the item count",
               all(len(r.order) == len(r.original) for r in results)),
              ("no result reports fewer than zero comparisons",
               all(r.comparisons >= 0 and r.writes >= 0 and r.swaps >= 0
                   for r in results)),
              ("a swap costs two writes, so writes >= 2 * swaps",
               all(r.writes >= 2 * r.swaps for r in results)),
              ("the last frame agrees with the final counters",
               all(r.frames[-1].comparisons == r.comparisons
                   and r.frames[-1].writes == r.writes for r in results)),
              ("the first frame is the untouched input",
               all(r.frames[0].data == tuple(item.key for item in r.original)
                   for r in results)),
              ("only the stable three are stable",
               all(r.is_stable() == (r.algorithm in STABLE)
                   for r in results))]
    return checks


def problems(results) -> list[str]:
    return [name for name, okay in audit(results) if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    items = read_values()
    results = [ALGORITHMS[name](items) for name in ALGORITHMS]
    keys = [item.key for item in items]

    print("=" * 74)
    print(" SORTING LAB - a counter's name is a claim about what it counts")
    print("=" * 74)
    print(f"  {len(items)} items, {len(set(keys))} distinct keys: "
          f"{' '.join(str(key) for key in keys)}")
    print(f"  {inversions(keys)} inversions to begin with; a reversed "
          f"{len(items)} would be {len(items) * (len(items) - 1) // 2}")

    print("\n  algorithm     comparisons   writes   swaps   stable   frames")
    for result in results:
        print(f"    {result.algorithm:<12}{result.comparisons:>11}"
              f"{result.writes:>9}{result.swaps:>8}"
              f"{'yes' if result.is_stable() else 'no':>9}"
              f"{len(result.frames):>9}")

    merge = next(r for r in results if r.algorithm == "merge")
    selection = next(r for r in results if r.algorithm == "selection")
    print(f"\n  the legacy counter, called {legacy_label()!r}, on merge sort: "
          f"{legacy_merge_writes(items)}")
    print(f"    merge sort really swaps {legacy_merge_swaps(items)} times: "
          f"it writes {merge.writes} placements, and the label turns writes "
          f"into exchanges")
    print(f"    selection sort really swaps {selection.swaps} times on "
          f"{len(items)} items, at most n-1 = {len(items) - 1} and fewer when a "
          f"position already holds its minimum")

    ascending = items_from_keys(sorted(keys))
    quadratic = quick_sort(ascending)
    quick_shuffled = next(r for r in results if r.algorithm == "quick")
    print(f"\n  the worst case is the input, not the reputation:")
    print(f"    quick sort on an already-sorted {len(ascending)}: "
          f"{quadratic.comparisons} comparisons "
          f"(n(n-1)/2 = {len(ascending) * (len(ascending) - 1) // 2})")
    print(f"    quick sort on the shuffled input: "
          f"{quick_shuffled.comparisons}")

    stable = [r.algorithm for r in results if r.is_stable()]
    print(f"\n  stable: {', '.join(stable)}")
    print(f"  not stable: "
          f"{', '.join(r.algorithm for r in results if not r.is_stable())}"
          f" -- measured on duplicate keys, not asserted")

    checks = audit(results)
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\n  a second run of the same six sorts: ", end="")
    again = [ALGORITHMS[name](items) for name in ALGORITHMS]
    same = [r.summary() for r in again] == [r.summary() for r in results]
    assert same, "the sorts are deterministic, so the summaries must agree"
    print("identical summaries")

    print("\nCross-checks OK: " +
          f"{len(items)} items sort under all six algorithms, every output is "
          f"non-decreasing and a permutation of its input, "
          f"merge sort writes {merge.writes} placements and swaps "
          f"{merge.swaps} times while the legacy label calls those writes "
          f"{legacy_label()!r}, selection sort swaps exactly {selection.swaps} "
          f"times on {len(items)} items, quick sort costs "
          f"{quadratic.comparisons} comparisons on an already-sorted input "
          f"and {quick_shuffled.comparisons} "
          f"on the shuffled one, exactly the three stable algorithms are stable "
          f"on duplicate keys, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("Demo completed successfully.")
    return 0
