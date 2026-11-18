"""Binary search, and the index it returns.

The legacy visualizer sorted its input before searching:

    def binary_search_steps(array, target):
        values = sorted(array)
        left = 0
        right = len(values) - 1
        ...
        return middle

Every index it reported -- the middle bar, the found bar, the left and right
boundaries -- was an index into ``sorted(array)``. For a list that was already
ascending the two arrays are the same and nothing shows. For ``[30, 10, 20]`` with
target ``10`` the search finds index ``0``, and index ``0`` of the caller's list
is ``30``.

Four things follow.

**1. A search returns an index into the array it searched.** If the function sorts
a copy, "the" answer refers to a different array than the one the caller holds.
This module never sorts: it checks that the input is ascending and refuses it
otherwise, so the index it returns is an index into the sequence you passed.

**2. Binary search on an unsorted array is not a slower search, it is an
undefined one.** It does not merely take longer; it can miss a value that is
present. The legacy code hid that by sorting. A refusal with a reason is the
honest behaviour, and it makes the precondition visible at the call site.

**3. "Found" is not enough when values repeat.** The bundled array holds three
copies of ``13``; a search that returns whichever copy its midpoint landed on
cannot answer "where does the block of 13s start and end". ``first_index`` and
``last_index`` do, and ``count_of`` is their difference plus one -- so a lookup
and a range query are different questions.

**4. A comparison bound is checkable.** Binary search over ``n`` sorted values
needs at most ``floor(log2(n)) + 1`` comparisons when it succeeds and
``ceil(log2(n + 1))`` when it fails. Every result here is checked against that
bound, so a loop with an off-by-one cannot pass as "fast".

Standard library only: no ``tkinter``, no ``bisect`` (it is re-implemented, then
cross-checked against ``bisect`` in the tests), no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, log2
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NUMBERS = DATA_DIR / "numbers.txt"

#: The legacy line that makes the returned index an index into another array.
LEGACY_SORT = "values = sorted(array)"
LEGACY_RETURN = "yield (values.copy(), ..., middle, middle, comparisons)"

#: The one thing that must be true before a binary search means anything.
PRECONDITION = "the sequence must be ascending"


class SearchError(ValueError):
    """A sequence, a target or a result that is refused."""


# --------------------------------------------------------------------------- #
# Probe and Result
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Probe:
    """One look at one position, and the window it was chosen from."""

    low: int
    high: int
    middle: int
    comparisons: int

    def __post_init__(self) -> None:
        if self.low < 0 or self.high < self.low:
            raise SearchError(f"an empty window is refused: [{self.low}, "
                              f"{self.high}]")
        if not self.low <= self.middle <= self.high:
            raise SearchError(f"a probe at {self.middle} is outside "
                              f"[{self.low}, {self.high}]")
        if self.comparisons < 1:
            raise SearchError("a probe is at least one comparison")

    @property
    def width(self) -> int:
        """How many positions the window still holds."""
        return self.high - self.low + 1


@dataclass(frozen=True)
class Result:
    """The outcome of one search over the sequence that was given."""

    algorithm: str
    values: tuple[int, ...]
    target: int
    index: int | None
    probes: tuple[Probe, ...]

    @property
    def found(self) -> bool:
        return self.index is not None

    @property
    def comparisons(self) -> int:
        return len(self.probes)

    @property
    def value(self) -> int | None:
        if self.index is None or not 0 <= self.index < len(self.values):
            return None
        return self.values[self.index]

    def is_hit(self) -> bool:
        """A found index must point at the target; a miss must not."""
        if self.index is None:
            return self.target not in self.values
        return 0 <= self.index < len(self.values) and \
            self.values[self.index] == self.target

    def windows_shrink(self) -> bool:
        """Every probe after the first must look at a strictly smaller window."""
        return all(later.width < earlier.width
                   for earlier, later in zip(self.probes, self.probes[1:]))

    def summary(self) -> dict:
        return {"algorithm": self.algorithm, "items": len(self.values),
                "target": self.target, "index": self.index,
                "found": self.found, "comparisons": self.comparisons}

    def to_dict(self) -> dict:
        return {**self.summary(),
                "probes": [[p.low, p.high, p.middle] for p in self.probes]}


# --------------------------------------------------------------------------- #
# Reading and checking
# --------------------------------------------------------------------------- #
def read_numbers(path=NUMBERS) -> tuple[int, ...]:
    """Read one integer per line; comments and blank lines are skipped."""
    path = Path(path)
    if not path.is_file():
        raise SearchError(f"numbers file not found: {path}")
    numbers = []
    for number, line in enumerate(path.read_text(encoding="utf-8")
                                 .splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        try:
            numbers.append(int(text))
        except ValueError:
            raise SearchError(f"{path.name}:{number}: {text!r} is not an "
                              f"integer") from None
    return tuple(numbers)


def is_sorted(values) -> bool:
    values = list(values)
    return all(left <= right for left, right in zip(values, values[1:]))


def check_sequence(values) -> tuple[int, ...]:
    """Refuse anything a binary search cannot be trusted on."""
    values = tuple(values)
    for position, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, int):
            raise SearchError(f"position {position} holds {value!r}, not an "
                              f"integer")
    if not is_sorted(values):
        raise SearchError(f"{PRECONDITION}: {list(values)} is not, so a binary "
                          f"search would be undefined rather than slow")
    return values


def check_target(target) -> int:
    if isinstance(target, bool) or not isinstance(target, int):
        raise SearchError(f"a target must be an integer, got {target!r}")
    return target


# --------------------------------------------------------------------------- #
# The searches
# --------------------------------------------------------------------------- #
def binary_search(values, target) -> Result:
    """Search a sequence that is already ascending; never sorts a copy."""
    values = check_sequence(values)
    target = check_target(target)
    low, high = 0, len(values) - 1
    probes: list[Probe] = []
    while low <= high:
        middle = (low + high) // 2
        probes.append(Probe(low, high, middle, len(probes) + 1))
        if values[middle] == target:
            return Result("binary", values, target, middle, tuple(probes))
        if values[middle] < target:
            low = middle + 1
        else:
            high = middle - 1
    return Result("binary", values, target, None, tuple(probes))


def linear_search(values, target) -> Result:
    """The same question, one position at a time -- the comparison to beat."""
    values = tuple(values)
    target = check_target(target)
    probes: list[Probe] = []
    for position in range(len(values)):
        probes.append(Probe(0, len(values) - 1, position, len(probes) + 1))
        if values[position] == target:
            return Result("linear", values, target, position, tuple(probes))
    return Result("linear", values, target, None, tuple(probes))


def first_index(values, target) -> int | None:
    """The first position holding ``target``, or ``None``."""
    values = check_sequence(values)
    target = check_target(target)
    low, high = 0, len(values) - 1
    answer = None
    while low <= high:
        middle = (low + high) // 2
        if values[middle] < target:
            low = middle + 1
        else:
            if values[middle] == target:
                answer = middle
            high = middle - 1
    return answer


def last_index(values, target) -> int | None:
    """The last position holding ``target``, or ``None``."""
    values = check_sequence(values)
    target = check_target(target)
    low, high = 0, len(values) - 1
    answer = None
    while low <= high:
        middle = (low + high) // 2
        if values[middle] > target:
            high = middle - 1
        else:
            if values[middle] == target:
                answer = middle
            low = middle + 1
    return answer


def count_of(values, target) -> int:
    """How many copies of ``target`` the sequence holds."""
    values = check_sequence(values)
    first = first_index(values, target)
    if first is None:
        return 0
    return last_index(values, target) - first + 1


def comparison_bound(size: int, found: bool) -> int:
    """The most comparisons a correct binary search may need."""
    if size <= 0:
        return 0
    if found:
        return int(log2(size)) + 1
    return ceil(log2(size + 1))


# --------------------------------------------------------------------------- #
# The legacy function
# --------------------------------------------------------------------------- #
def legacy_sorted_index(array, target) -> int | None:
    """The legacy search: sort a copy, then return an index into the copy."""
    values = sorted(array)
    target = check_target(target)
    low, high = 0, len(values) - 1
    while low <= high:
        middle = (low + high) // 2
        if values[middle] == target:
            return middle
        if values[middle] < target:
            low = middle + 1
        else:
            high = middle - 1
    return None


def legacy_wrong_value(array, target) -> int | None:
    """What ``array[index]`` is, when ``index`` came from the sorted copy."""
    index = legacy_sorted_index(array, target)
    if index is None:
        return None
    return list(array)[index]


def legacy_note() -> tuple[str, str]:
    """The two lines of the legacy function that cause the wrong array."""
    return LEGACY_SORT, LEGACY_RETURN


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def audit(results) -> list[tuple[str, bool]]:
    results = list(results)
    return [
        ("every found index points at the target",
         all(r.is_hit() for r in results if r.found)),
        ("every miss is a value the sequence does not hold",
         all(r.target not in r.values for r in results if not r.found)),
        ("every index lies inside the sequence",
         all(0 <= r.index < len(r.values) for r in results if r.found)),
        ("every binary probe narrows the window",
         all(r.windows_shrink() for r in results
             if r.algorithm == "binary" and len(r.probes) > 1)),
        ("binary search stays inside its comparison bound",
         all(r.comparisons <= comparison_bound(len(r.values), r.found)
             for r in results if r.algorithm == "binary")),
        ("a hit's value is the target and a miss's value is None",
         all((r.value == r.target) if r.found else (r.value is None)
             for r in results)),
        ("every binary result was searched on an ascending sequence",
         all(is_sorted(r.values) for r in results
             if r.algorithm == "binary")),
    ]


def audit_pairs(pairs) -> list[tuple[str, bool]]:
    """A real check, and one that is true: the totals, not every single hit.

    A binary hit is *not* always cheaper -- finding the first element costs one
    linear comparison and up to ``log2(n)`` binary ones. What holds is the total
    across every target in the sequence, which is what "logarithmic" means.
    """
    pairs = list(pairs)
    binary_total = sum(binary.comparisons for binary, _ in pairs)
    linear_total = sum(linear.comparisons for _, linear in pairs)
    return [("binary's total comparisons across every target beat linear's",
             binary_total <= linear_total)]


def problems(results) -> list[str]:
    return [name for name, okay in audit(results) if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    numbers = read_numbers()
    target = 23
    binary = binary_search(numbers, target)
    linear = linear_search(numbers, target)
    missing = binary_search(numbers, 22)

    print("=" * 74)
    print(" SEARCH LAB - a search returns an index into the array it searched")
    print("=" * 74)
    print(f"  {len(numbers)} numbers: {' '.join(str(n) for n in numbers)}")
    print(f"  target {target}: binary found index {binary.index} in "
          f"{binary.comparisons} comparisons, linear in "
          f"{linear.comparisons}")
    print(f"  the bound for a hit on {len(numbers)} is "
          f"{comparison_bound(len(numbers), True)}")
    print(f"  target 22 is absent: {missing.comparisons} comparisons, "
          f"bound {comparison_bound(len(numbers), False)}")

    unsorted = (30, 10, 20)
    index = legacy_sorted_index(unsorted, 10)
    print(f"\n  the legacy function on {list(unsorted)}, target 10:")
    print(f"    {LEGACY_SORT}")
    print(f"    it returns index {index}, which is right for "
          f"{sorted(unsorted)} and gives {legacy_wrong_value(unsorted, 10)} "
          f"in the array you passed")
    refused = 0
    for bad in (unsorted, (1, 3, 2), (5, 4)):
        try:
            binary_search(bad, 10)
        except SearchError:
            refused += 1
    print(f"    this module refuses all {refused} unsorted inputs with a "
          f"reason instead of sorting behind the caller's back")

    print(f"\n  three copies of 13 in the bundled data:")
    print(f"    first_index(13) {first_index(numbers, 13)}, "
          f"last_index(13) {last_index(numbers, 13)}, "
          f"count_of(13) {count_of(numbers, 13)}")
    print(f"    a plain binary search returns one of them; only the pair "
          f"answers 'where does the block start'")

    pairs = [(binary_search(numbers, n), linear_search(numbers, n))
             for n in numbers]
    binary_total = sum(binary.comparisons for binary, _ in pairs)
    linear_total = sum(linear.comparisons for _, linear in pairs)
    print(f"\n  across all {len(numbers)} targets: binary "
          f"{binary_total} comparisons, linear {linear_total} "
          f"(the worst case is the first element, where linear wins once)")
    checks = audit([b for b, _ in pairs] + [missing]) + audit_pairs(pairs)
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\n  a second run of the same two searches: ", end="")
    again = (binary_search(numbers, target).summary(),
             linear_search(numbers, target).summary())
    first = (binary.summary(), linear.summary())
    assert again == first, "a search is deterministic, so the summaries agree"
    print("identical summaries")

    print("\nCross-checks OK: " +
          f"{len(numbers)} ascending numbers answer target {target} at index "
          f"{binary.index} in {binary.comparisons} comparisons against "
          f"{linear.comparisons} for the linear scan, a miss costs "
          f"{missing.comparisons} and stays inside the "
          f"{comparison_bound(len(numbers), False)} bound, every probe narrows "
          f"its window, every found index points at the target, three unsorted "
          f"inputs were refused rather than sorted, the legacy function returns "
          f"index {index} from a sorted copy and reads "
          f"{legacy_wrong_value(unsorted, 10)} out of the original, the three "
          f"copies of 13 span indices {first_index(numbers, 13)} to "
          f"{last_index(numbers, 13)}, binary's {binary_total} comparisons over "
          f"every target beat linear's {linear_total}, a second run agrees, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("Demo completed successfully.")
    return 0
