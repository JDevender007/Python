"""A load balancer that never overlaps a request measures an empty queue.

The legacy balancer is built from three honest-looking lines:

    self.active += 1
    ok = rng.random() >= self.failure_rate
    self.active -= 1

and a chooser:

    return min(pool, key=lambda b: (b.active, b.name))

Each line is correct on its own. Together they are a load balancer that always
picks the alphabetically first backend.

**1. A counter incremented and decremented inside one call is not a
measurement.** `serve()` is synchronous: by the time the next request is
dispatched, every backend's `active` is back to zero. `least_connections`
therefore sees `(0, "alpha"), (0, "beta"), (0, "gamma")` for every single
request and sends all **12** of them to `alpha`, whose queue ends at **48**
ticks while its two peers finish at **0**. Concurrency is not a detail of
least-connections; it is the quantity the strategy is named after.

**2. A weight is capacity, not a request count.** Round-robin gives `alpha`,
`beta` and `gamma` four requests each. With weights 1, 2 and 1 that is 16, 16
and 16 units of work against fair shares of 12, 24 and 12: `alpha` and `gamma`
run at **1333 permille** of their capacity and `beta` at **667**. Splitting
requests evenly is not balancing load; it is balancing *counts*.

**3. Fairness is not `max - min`.** The legacy fairness score is
`max(counts) - min(counts)`, which calls the 4/4/4 split **perfect** -- spread
0 -- although `alpha` and `gamma` each carry **1333 permille** of their
capacity while `beta` carries 667. Jain's index over the capacity-normalised
load scores that split **926**: nearly fair, and completely blind to the fact
that two of the three backends are saturated. A fairness index is scale-free;
it compares backends to each other, never to their own limit. The rebuild
therefore reports both: the index for balance, and the **maximum load ratio**
for saturation. The same split is balanced by neither measure.

**4. A percentage is an apportionment, not a division.** `100 * count / total`
formatted to one decimal prints `33.3%` three times for a 4/4/4 split, and the
three lines sum to **99.9**. The rebuild apportions 1000 permille with the
largest-remainder method: **334 + 333 + 333 = 1000**, exactly, every time.

The simulation is discrete and integer: backends complete `weight` work units
per tick, a request finishes at `ceil(assigned_work / weight)`, and no clock,
socket, float or random number is involved. Twelve requests of four units run
against three backends weighted 1, 2 and 1, and every number in the demo is
reproducible from `data/scenario.json`.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCENARIO_FILE = DATA_DIR / "scenario.json"

#: The four policies the lab compares, in report order.
POLICIES = ("round_robin", "smooth_weighted", "legacy_least_connections", "least_load")

#: The legacy shortcuts, transcribed so the demo can print them.
LEGACY_ACTIVE = "self.active += 1 ... self.active -= 1   # within one call"
LEGACY_CHOOSE = "min(pool, key=lambda b: (b.active, b.name))"
LEGACY_FAIRNESS = "fairness = max(counts) - min(counts)  # 0 means perfect"
LEGACY_SHARE = 'f"{100 * count / total:.1f}%"           # 33.3 + 33.3 + 33.3'

MAX_BACKENDS = 32
MAX_REQUESTS = 512
MAX_WEIGHT = 64
MAX_WORK = 1024
SLUG = re.compile(r"^[a-z][a-z0-9-]{0,30}$")


class ScenarioError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Arithmetic
# --------------------------------------------------------------------------- #
def divide_half_up(numerator: int, denominator: int) -> int:
    """Round a non-negative ratio half away from zero, on integers only."""
    if denominator <= 0:
        raise ScenarioError("a divisor must be positive")
    if numerator < 0:
        raise ScenarioError("a dividend must be non-negative")
    return (2 * numerator + denominator) // (2 * denominator)


def ceil_div(numerator: int, denominator: int) -> int:
    """The smallest integer not below the exact ratio."""
    if denominator <= 0:
        raise ScenarioError("a divisor must be positive")
    return -(-numerator // denominator)


def jain_permille(values: Iterable[int]) -> int:
    """Jain's fairness index in permille: S^2 / (n * Q), rounded half up."""
    numbers = [int(value) for value in values]
    if not numbers or any(value < 0 for value in numbers):
        raise ScenarioError("Jain's index needs non-negative values")
    total = sum(numbers)
    squares = sum(value * value for value in numbers)
    if total == 0 or squares == 0:
        return 0
    return divide_half_up(1000 * total * total, len(numbers) * squares)


def apportion_permille(parts: Iterable[int]) -> list[int]:
    """Split 1000 permille by largest remainder; the result always sums to 1000."""
    numbers = [int(value) for value in parts]
    if any(value < 0 for value in numbers):
        raise ScenarioError("an apportionment needs non-negative parts")
    total = sum(numbers)
    if total == 0:
        return [0 for _ in numbers]
    base = [(1000 * value) // total for value in numbers]
    remainders = [(1000 * value) % total for value in numbers]
    left = 1000 - sum(base)
    order = sorted(range(len(numbers)), key=lambda index: (-remainders[index], index))
    for index in order[:left]:
        base[index] += 1
    return base


def legacy_shares(counts: Iterable[int]) -> list[float]:
    """The floating-percentage shortcut, kept so its 99.9 can be printed."""
    numbers = [int(value) for value in counts]
    total = sum(numbers)
    if total == 0:
        return [0.0 for _ in numbers]
    return [round(100.0 * value / total, 1) for value in numbers]


def spread(counts: Iterable[int]) -> int:
    """The legacy fairness score: largest count minus smallest."""
    numbers = [int(value) for value in counts]
    if not numbers:
        return 0
    return max(numbers) - min(numbers)


def legacy_verdict(counts: Iterable[int]) -> str:
    """The legacy verdict, which only ever looks at counts."""
    return "perfect" if spread(counts) == 0 else "uneven"


def capacity_verdict(max_load: int) -> str:
    """A verdict that looks at the busiest backend's share of its capacity."""
    if max_load <= 1050:
        return "balanced"
    if max_load <= 1250:
        return "acceptable"
    return "overloaded"


def max_load_permille(run: "Run") -> int:
    """The busiest backend's work as permille of its fair share."""
    total_work = sum(run.work)
    total_weight = sum(run.weights)
    if total_work == 0 or total_weight == 0:
        return 0
    return max(
        divide_half_up(1000 * work * total_weight, total_work * weight)
        for work, weight in zip(run.work, run.weights)
    )


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Backend:
    name: str
    weight: int

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "weight": self.weight}


@dataclass(frozen=True)
class Request:
    name: str
    work: int

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "work": self.work}


@dataclass(frozen=True)
class Scenario:
    name: str
    backends: tuple[Backend, ...]
    requests: tuple[Request, ...]


@dataclass(frozen=True)
class Placement:
    request: str
    backend: str
    finish: int


@dataclass(frozen=True)
class Run:
    """One policy applied to one scenario: counts, work and finish ticks."""

    policy: str
    names: tuple[str, ...]
    counts: tuple[int, ...]
    work: tuple[int, ...]
    finishes: tuple[tuple[int, ...], ...]
    placements: tuple[Placement, ...]
    weights: tuple[int, ...] = ()
    samples: tuple[tuple[int, ...], ...] = ()

    @property
    def makespan(self) -> int:
        return max((ticks[-1] for ticks in self.finishes if ticks), default=0)

    @property
    def total_finish(self) -> int:
        return sum(sum(ticks) for ticks in self.finishes)

    @property
    def shares(self) -> tuple[int, ...]:
        return tuple(apportion_permille(self.counts))

    @property
    def jain_counts(self) -> int:
        return jain_permille(self.counts)

    @property
    def jain_capacity(self) -> int:
        if not self.weights:
            return jain_permille(self.counts)
        common = math.lcm(*self.weights)
        loads = [
            count * (common // weight)
            for count, weight in zip(self.counts, self.weights)
        ]
        return jain_permille(loads)

    @property
    def max_load(self) -> int:
        return max_load_permille(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "names": list(self.names),
            "weights": list(self.weights),
            "counts": list(self.counts),
            "work": list(self.work),
            "finishes": [list(ticks) for ticks in self.finishes],
            "makespan": self.makespan,
            "total_finish": self.total_finish,
            "shares": list(self.shares),
            "jain_counts": self.jain_counts,
            "jain_capacity": self.jain_capacity,
            "max_load": self.max_load,
            "spread": spread(self.counts),
            "legacy_verdict": legacy_verdict(self.counts),
            "capacity_verdict": capacity_verdict(self.max_load),
            "placements": [
                {"request": item.request, "backend": item.backend, "finish": item.finish}
                for item in self.placements
            ],
        }



# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #
def load_document(path: str | Path) -> dict[str, Any]:
    """Read one ASCII JSON document and require a mapping at the root."""
    target = Path(path)
    if not target.is_file():
        raise ScenarioError(f"scenario not found: {target.name}")
    try:
        body = target.read_bytes().decode("ascii")
    except UnicodeDecodeError as exc:
        raise ScenarioError(f"{target.name} is not ASCII text") from exc
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ScenarioError(f"{target.name} is not valid JSON: line {exc.lineno}") from exc
    if not isinstance(data, dict):
        raise ScenarioError(f"{target.name}: a scenario root must be a mapping")
    return data


def read_scenario(path: str | Path | None = None) -> Scenario:
    """Load the bundled scenario, or one named on the command line."""
    document = load_document(path if path is not None else SCENARIO_FILE)
    return scenario_from_document(document)


def scenario_from_document(document: dict[str, Any]) -> Scenario:
    """Convert a parsed document into records without trusting its shape."""
    name = document.get("name", "scenario")
    backends_raw = document.get("backends")
    requests_raw = document.get("requests")
    backends: list[Backend] = []
    if isinstance(backends_raw, list):
        for item in backends_raw:
            if isinstance(item, dict):
                backends.append(Backend(str(item.get("name", "")), _as_int(item.get("weight", 0))))
    requests: list[Request] = []
    if isinstance(requests_raw, list):
        for item in requests_raw:
            if isinstance(item, dict):
                requests.append(Request(str(item.get("name", "")), _as_int(item.get("work", 0))))
    return Scenario(str(name), tuple(backends), tuple(requests))


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def validate_scenario(scenario: Scenario) -> list[str]:
    """Every problem with a parsed scenario; an empty list means valid."""
    problems: list[str] = []
    if not isinstance(scenario.name, str) or not SLUG.match(scenario.name):
        problems.append("$.name: a lowercase slug is required")
    if not scenario.backends:
        problems.append("$.backends: a non-empty array is required")
    elif len(scenario.backends) > MAX_BACKENDS:
        problems.append(f"$.backends: at most {MAX_BACKENDS} backends")
    seen: set[str] = set()
    for index, backend in enumerate(scenario.backends):
        where = f"$.backends[{index}]"
        if not SLUG.match(backend.name):
            problems.append(f"{where}.name: a lowercase slug is required")
        elif backend.name in seen:
            problems.append(f"{where}.name: duplicate backend {backend.name!r}")
        else:
            seen.add(backend.name)
        if not 1 <= backend.weight <= MAX_WEIGHT:
            problems.append(f"{where}.weight: an integer 1..{MAX_WEIGHT} is required")
    if not scenario.requests:
        problems.append("$.requests: a non-empty array is required")
    elif len(scenario.requests) > MAX_REQUESTS:
        problems.append(f"$.requests: at most {MAX_REQUESTS} requests")
    seen_requests: set[str] = set()
    for index, request in enumerate(scenario.requests):
        where = f"$.requests[{index}]"
        if not request.name:
            problems.append(f"{where}.name: a request identifier is required")
        elif request.name in seen_requests:
            problems.append(f"{where}.name: duplicate request {request.name!r}")
        else:
            seen_requests.add(request.name)
        if not 1 <= request.work <= MAX_WORK:
            problems.append(f"{where}.work: an integer 1..{MAX_WORK} is required")
    return problems


def validate_or_raise(scenario: Scenario) -> None:
    problems = validate_scenario(scenario)
    if problems:
        joined = "\n  - ".join(problems)
        raise ScenarioError(f"invalid scenario ({len(problems)} problem(s)):\n  - {joined}")


# --------------------------------------------------------------------------- #
# Policies
# --------------------------------------------------------------------------- #
def _smooth_weighted_index(current: list[int], weights: list[int]) -> int:
    """nginx-style smooth weighted round-robin over every backend."""
    total = sum(weights)
    for index, weight in enumerate(weights):
        current[index] += weight
    best = 0
    for index in range(1, len(current)):
        if current[index] > current[best]:
            best = index
    current[best] -= total
    return best


def simulate(scenario: Scenario, policy: str) -> Run:
    """Assign every request in order and record when each one finishes."""
    if policy not in POLICIES:
        raise ScenarioError(f"unknown policy {policy!r} (choose {', '.join(POLICIES)})")
    validate_or_raise(scenario)
    names = [backend.name for backend in scenario.backends]
    weights = [backend.weight for backend in scenario.backends]
    count = len(names)

    counts = [0] * count
    work = [0] * count
    finishes: list[list[int]] = [[] for _ in range(count)]
    placements: list[Placement] = []
    samples: list[tuple[int, ...]] = []
    current = [0] * count
    active = [0] * count

    for index, request in enumerate(scenario.requests):
        if policy == "round_robin":
            chosen = index % count
        elif policy == "smooth_weighted":
            chosen = _smooth_weighted_index(current, weights)
        elif policy == "legacy_least_connections":
            # The legacy serve() holds this connection only for the length of
            # one synchronous call, so the sample below is always all zeros.
            samples.append(tuple(active))
            chosen = min(range(count), key=lambda slot: (active[slot], names[slot]))
            active[chosen] += 1
            active[chosen] -= 1
        else:
            chosen = min(
                range(count),
                key=lambda slot: (
                    ceil_div(work[slot] + request.work, weights[slot]),
                    names[slot],
                ),
            )

        counts[chosen] += 1
        work[chosen] += request.work
        tick = ceil_div(work[chosen], weights[chosen])
        finishes[chosen].append(tick)
        placements.append(Placement(request.name, names[chosen], tick))

    run = Run(
        policy=policy,
        names=tuple(names),
        counts=tuple(counts),
        work=tuple(work),
        finishes=tuple(tuple(ticks) for ticks in finishes),
        placements=tuple(placements),
        weights=tuple(weights),
        samples=tuple(samples),
    )
    return run


def legacy_fairness(run: Run) -> dict[str, Any]:
    """The legacy score and its verdict, which disagree with capacity Jain."""
    score = spread(run.counts)
    return {
        "spread": score,
        "verdict": "perfect" if score == 0 else "uneven",
        "jain_capacity": run.jain_capacity,
        "max_load": run.max_load,
        "load_verdict": capacity_verdict(run.max_load),
    }


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(scenario_path: str | Path | None = None) -> dict[str, Any]:
    scenario = read_scenario(scenario_path)
    validate_or_raise(scenario)
    runs = {policy: simulate(scenario, policy) for policy in POLICIES}
    return {
        "scenario": scenario,
        "runs": runs,
        "float_shares": {
            policy: legacy_shares(run.counts) for policy, run in runs.items()
        },
        "float_totals": {
            policy: round(sum(legacy_shares(run.counts)), 1) for policy, run in runs.items()
        },
    }


def report(measured: dict[str, Any]) -> dict[str, Any]:
    """A JSON-safe view: no dataclass survives, only numbers and lists."""
    scenario: Scenario = measured["scenario"]
    return {
        "scenario": scenario.name,
        "backends": [backend.to_dict() for backend in scenario.backends],
        "requests": [request.to_dict() for request in scenario.requests],
        "runs": {
            policy: run.to_dict() for policy, run in measured["runs"].items()
        },
        "float_shares": measured["float_shares"],
        "float_totals": measured["float_totals"],
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
    except ScenarioError:
        return True
    return False


def audit(
    measured: dict[str, Any],
    *,
    read: Callable[[], Scenario] = read_scenario,
    run: Callable[[Scenario, str], Run] = simulate,
) -> list[tuple[str, bool]]:
    """Every check rebuilds the four runs from the scenario, not the summary."""
    cache: dict[str, Any] = {}

    def rebuilt() -> dict[str, Any]:
        if not cache:
            scenario = read()
            cache["scenario"] = scenario
            cache["runs"] = {policy: run(scenario, policy) for policy in POLICIES}
        return cache

    def counts(policy: str) -> list[int]:
        return list(rebuilt()["runs"][policy].counts)

    def pinned(policy: str, expected: list[int]) -> bool:
        return counts(policy) == expected == list(measured["runs"][policy].counts)

    checks = [
        (
            "the_scenario_reads_and_validates",
            lambda: validate_scenario(rebuilt()["scenario"]) == []
            and len(rebuilt()["scenario"].backends) == 3,
        ),
        (
            "the_bundled_scenario_is_pinned",
            lambda: [backend.weight for backend in rebuilt()["scenario"].backends]
            == [1, 2, 1]
            and len(rebuilt()["scenario"].requests) == 12
            and all(request.work == 4 for request in rebuilt()["scenario"].requests),
        ),
        (
            "round_robin_serves_equal_counts",
            lambda: pinned("round_robin", [4, 4, 4]),
        ),
        (
            "a_weight_is_capacity_not_a_count",
            lambda: pinned("smooth_weighted", [3, 6, 3])
            and [backend.weight for backend in rebuilt()["scenario"].backends]
            == [1, 2, 1],
        ),
        (
            "least_load_splits_work_by_capacity",
            lambda: pinned("least_load", [3, 6, 3])
            and rebuilt()["runs"]["least_load"].jain_capacity
            == measured["runs"]["least_load"].jain_capacity
            == 1000,
        ),
        (
            "the_in_flight_counter_is_always_zero",
            lambda: counts("legacy_least_connections") == [12, 0, 0]
            and all(
                sample == (0, 0, 0)
                for sample in rebuilt()["runs"]["legacy_least_connections"].samples
            ),
        ),
        (
            "the_broken_counter_costs_the_makespan",
            lambda: [
                rebuilt()["runs"][policy].makespan
                for policy in ("least_load", "round_robin", "legacy_least_connections")
            ]
            == [12, 16, 48]
            == [
                measured["runs"][policy].makespan
                for policy in ("least_load", "round_robin", "legacy_least_connections")
            ],
        ),
        (
            "jains_index_is_scale_free",
            lambda: [
                rebuilt()["runs"][policy].jain_counts
                for policy in ("round_robin", "least_load", "legacy_least_connections")
            ]
            == [1000, 889, 333]
            == [
                measured["runs"][policy].jain_counts
                for policy in ("round_robin", "least_load", "legacy_least_connections")
            ],
        ),
        (
            "capacity_jain_separates_equal_counts_from_equal_load",
            lambda: [
                (
                    rebuilt()["runs"][policy].jain_capacity,
                    rebuilt()["runs"][policy].max_load,
                )
                for policy in ("round_robin", "least_load", "smooth_weighted")
            ]
            == [(926, 1333), (1000, 1000), (1000, 1000)]
            == [
                (
                    measured["runs"][policy].jain_capacity,
                    measured["runs"][policy].max_load,
                )
                for policy in ("round_robin", "least_load", "smooth_weighted")
            ],
        ),
        (
            "the_legacy_spread_calls_equal_counts_perfect",
            lambda: legacy_fairness(rebuilt()["runs"]["round_robin"])["spread"]
            == spread(measured["runs"]["round_robin"].counts)
            == 0
            and legacy_fairness(rebuilt()["runs"]["round_robin"])["verdict"] == "perfect"
            and legacy_fairness(rebuilt()["runs"]["round_robin"])["load_verdict"]
            == capacity_verdict(measured["runs"]["round_robin"].max_load)
            == "overloaded",
        ),
        (
            "apportioned_percentages_sum_to_one_thousand",
            lambda: all(sum(run.shares) == 1000 for run in rebuilt()["runs"].values())
            and rebuilt()["runs"]["round_robin"].shares
            == measured["runs"]["round_robin"].shares
            == (334, 333, 333)
            and round(sum(legacy_shares([4, 4, 4])), 1) == 99.9,
        ),
        (
            "round_robin_overloads_the_small_backend",
            lambda: list(rebuilt()["runs"]["round_robin"].work)
            == list(measured["runs"]["round_robin"].work)
            == [16, 16, 16]
            and list(rebuilt()["runs"]["least_load"].work)
            == list(measured["runs"]["least_load"].work)
            == [12, 24, 12],
        ),
        (
            "two_policies_can_agree_on_counts_and_differ_on_placement",
            lambda: counts("smooth_weighted") == counts("least_load")
            and [
                item.backend
                for item in rebuilt()["runs"]["smooth_weighted"].placements[:3]
            ]
            == [
                item.backend
                for item in measured["runs"]["smooth_weighted"].placements[:3]
            ]
            == ["beta", "alpha", "gamma"]
            and [
                item.backend for item in rebuilt()["runs"]["least_load"].placements[:3]
            ]
            == [
                item.backend for item in measured["runs"]["least_load"].placements[:3]
            ]
            == ["beta", "alpha", "beta"],
        ),
        (
            "a_bad_scenario_is_refused",
            lambda: _refused(
                lambda: simulate(
                    Scenario(
                        "bad",
                        (Backend("alpha", 0), Backend("beta", 1)),
                        (Request("r1", 4),),
                    ),
                    "least_load",
                )
            )
            and _refused(lambda: simulate(rebuilt()["scenario"], "magic"))
            and validate_scenario(
                Scenario(
                    "dup",
                    (Backend("alpha", 1), Backend("alpha", 1)),
                    (Request("r1", 4),),
                )
            )
            != [],
        ),
        (
            "the_rebuild_is_deterministic",
            lambda: all(
                rebuilt()["runs"][policy].counts == measured["runs"][policy].counts
                and rebuilt()["runs"][policy].placements
                == measured["runs"][policy].placements
                for policy in POLICIES
            ),
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_run(run: Run) -> str:
    """A fixed-width table for one policy; every figure is an integer."""
    lines = [
        f"Policy   : {run.policy}",
        f"Finished : makespan {run.makespan} ticks, total completion {run.total_finish}",
        f"Fairness : Jain(counts) {run.jain_counts} permille, "
        f"Jain(capacity) {run.jain_capacity} permille, "
        f"max load {run.max_load} permille "
        f"({capacity_verdict(run.max_load)})",
        "",
        f"{'Backend':<10} {'Weight':>6} {'Count':>6} {'Work':>6} {'Share':>7} "
        f"{'Last':>5}",
        "-" * 48,
    ]
    for index, name in enumerate(run.names):
        last = run.finishes[index][-1] if run.finishes[index] else 0
        lines.append(
            f"{name:<10} {run.weights[index]:>6} {run.counts[index]:>6} "
            f"{run.work[index]:>6} {run.shares[index]:>6}o/oo {last:>5}"
        )
    lines.append(
        f"{'':<10} {'':>6} {sum(run.counts):>6} {sum(run.work):>6} "
        f"{sum(run.shares):>6}o/oo"
    )
    return "\n".join(lines)


def run_demo(scenario_path: str | Path | None = None) -> int:
    measured = measure(scenario_path)
    scenario: Scenario = measured["scenario"]
    runs = measured["runs"]
    round_robin = runs["round_robin"]
    weighted = runs["smooth_weighted"]
    legacy = runs["legacy_least_connections"]
    least = runs["least_load"]

    print("Load balancer -- a queue is only visible if requests overlap")
    print("=" * 62)
    print()
    print(
        f"Scenario {scenario.name}: {len(scenario.backends)} backends, "
        f"{len(scenario.requests)} requests of "
        f"{scenario.requests[0].work} work units."
    )
    print(
        "Weights: "
        + ", ".join(f"{b.name} {b.weight}" for b in scenario.backends)
        + "; a backend completes `weight` units per tick."
    )
    print()
    print("1. A counter that never overlaps measures nothing.")
    print("   " + LEGACY_ACTIVE)
    print("   " + LEGACY_CHOOSE)
    print(
        f"   samples: {legacy.samples[0]} every time, so all "
        f"{sum(legacy.counts)} requests go to {legacy.names[0]}: counts "
        f"{_counts(legacy)}."
    )
    print(
        f"   makespan: least load {least.makespan}, round robin "
        f"{round_robin.makespan}, legacy {legacy.makespan} ticks."
    )
    print()
    print("2. A weight is capacity, not a request count.")
    print(
        f"   round robin counts {_counts(round_robin)} -> work "
        f"{_work(round_robin)} against capacity "
        f"{_capacity(scenario)}: max load "
        f"{round_robin.max_load} permille "
        f"({capacity_verdict(round_robin.max_load)})."
    )
    print(
        f"   smooth weighted counts {_counts(weighted)} -> work "
        f"{_work(weighted)}: max load {weighted.max_load} permille "
        f"({capacity_verdict(weighted.max_load)})."
    )
    print()
    print("3. Fairness is not max minus min.")
    print("   " + LEGACY_FAIRNESS)
    for policy in POLICIES:
        run = runs[policy]
        print(
            f"   {policy:<24} spread {spread(run.counts):>2}  "
            f"Jain(counts) {run.jain_counts:>4}  "
            f"Jain(capacity) {run.jain_capacity:>4}  "
            f"max load {run.max_load:>4}  "
            f"{capacity_verdict(run.max_load)}"
        )
    print(
        f"   the legacy score calls the {_counts(round_robin)} split "
        f"'{legacy_verdict(round_robin.counts)}' while its capacity Jain is "
        f"{round_robin.jain_capacity} and the busiest backend is at "
        f"{round_robin.max_load} permille."
    )
    print()
    print("4. A percentage is an apportionment.")
    print("   " + LEGACY_SHARE)
    float_shares = measured["float_shares"]["round_robin"]
    print(
        f"   float shares for {_counts(round_robin)}: "
        + " + ".join(f"{value:.1f}" for value in float_shares)
        + f" = {measured['float_totals']['round_robin']:.1f}%"
    )
    print(
        f"   permille shares: {' + '.join(str(v) for v in round_robin.shares)} = "
        f"{sum(round_robin.shares)}"
    )
    print()
    for policy in ("smooth_weighted", "least_load"):
        print(render_run(runs[policy]))
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
        f"round robin splits {_counts(round_robin)} and finishes at tick "
        f"{round_robin.makespan}, least load splits {_counts(least)} and "
        f"finishes at {least.makespan} with {least.jain_capacity} capacity "
        f"permille and a busiest backend at {least.max_load}, while the "
        f"legacy in-flight counter samples "
        f"{legacy.samples[0]} and sends all {sum(legacy.counts)} requests to "
        f"{legacy.names[0]} for a makespan of {legacy.makespan}; the max-minus-"
        f"min score calls the equal split "
        f"'{legacy_verdict(round_robin.counts)}' although capacity Jain is "
        f"{round_robin.jain_capacity} and its busiest backend runs at "
        f"{round_robin.max_load} permille; float shares sum to "
        f"{measured['float_totals']['round_robin']:.1f}% where apportioned "
        f"permille sums to {sum(round_robin.shares)}; "
        f"{passed}/{len(results)} checks pass."
    )
    print("Demo completed successfully.")
    return 0


def _counts(run: Run) -> str:
    return "/".join(str(value) for value in run.counts)


def _work(run: Run) -> str:
    return "/".join(str(value) for value in run.work)


def _capacity(scenario: Scenario) -> str:
    total_work = sum(request.work for request in scenario.requests)
    return "/".join(str(total_work * backend.weight) for backend in scenario.backends)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
