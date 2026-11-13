"""Grid path planning: A*, Dijkstra, RRT and line-of-sight smoothing.

A map is plain text: ``#`` is a wall, ``.`` is free, ``S`` marks the start
and ``G`` the goal.  Movement is 8-connected with costs 1 (orthogonal)
and sqrt(2) (diagonal); diagonal moves may not squeeze past two blocked
orthogonal neighbours unless corner cutting is explicitly allowed.

Three planners are provided:

* ``astar``     - best-first search with a configurable heuristic;
* ``dijkstra``  - A* with a zero heuristic, i.e. uniform-cost search;
* ``rrt``       - a seeded rapidly-exploring random tree.

Every planner returns a ``Plan`` with the path, its cost, and how many
nodes it expanded.  ``smooth_path`` shortcuts a path with line-of-sight
checks, and ``render_map`` draws the result as ASCII.

Fully offline: the bundled map lives in ``data/map.txt``.
"""

from __future__ import annotations

import heapq
import logging
import math
import random
from dataclasses import dataclass
from pathlib import Path

LOG = logging.getLogger("planner")

WALL = "#"
FREE = "."
START = "S"
GOAL = "G"
SYMBOLS = (WALL, FREE, START, GOAL)
ALGORITHMS = ("astar", "dijkstra", "rrt")
HEURISTICS = ("octile", "manhattan", "euclidean", "zero")
DIAGONAL_COST = math.sqrt(2.0)
EPS = 1e-9

ORTHOGONAL = ((-1, 0), (0, 1), (1, 0), (0, -1))
DIAGONAL = ((-1, 1), (1, 1), (1, -1), (-1, -1))

Point = tuple[int, int]


class PlannerError(RuntimeError):
    """Raised for invalid maps, bad flags and failed searches."""


# --------------------------------------------------------------------------- #
# Map model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class GridMap:
    """An immutable occupancy grid with one start and one goal cell."""

    cells: tuple[str, ...]
    start: Point
    goal: Point
    name: str = "map"

    @property
    def rows(self) -> int:
        return len(self.cells)

    @property
    def cols(self) -> int:
        return len(self.cells[0]) if self.cells else 0

    def in_bounds(self, point: Point) -> bool:
        row, col = point
        return 0 <= row < self.rows and 0 <= col < self.cols

    def is_free(self, point: Point) -> bool:
        return self.in_bounds(point) and self.cells[point[0]][point[1]] != WALL

    def is_wall(self, point: Point) -> bool:
        return self.in_bounds(point) and self.cells[point[0]][point[1]] == WALL

    def free_cells(self) -> int:
        return sum(row.count(FREE) for row in self.cells)

    def to_dict(self) -> dict:
        return {"name": self.name, "rows": self.rows, "cols": self.cols,
                "start": list(self.start), "goal": list(self.goal),
                "free_cells": self.free_cells()}


def parse_map(text: str, name: str = "map") -> GridMap:
    """Parse map text into a validated GridMap."""
    if not isinstance(text, str):
        raise PlannerError("map must be text")
    lines = [line.rstrip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise PlannerError("map is empty")

    width = len(lines[0])
    if width == 0:
        raise PlannerError("map rows must not be empty")
    for index, line in enumerate(lines):
        if len(line) != width:
            raise PlannerError(
                f"row {index} has {len(line)} column(s), expected {width}")

    bad = sorted({char for line in lines for char in line
                  if char not in SYMBOLS})
    if bad:
        raise PlannerError(
            f"unknown map symbol(s): {', '.join(repr(c) for c in bad)} "
            f"(allowed: {''.join(SYMBOLS)})")

    starts = [(r, c) for r, line in enumerate(lines)
              for c, char in enumerate(line) if char == START]
    goals = [(r, c) for r, line in enumerate(lines)
             for c, char in enumerate(line) if char == GOAL]
    if len(starts) != 1:
        raise PlannerError(f"map needs exactly one start, found {len(starts)}")
    if len(goals) != 1:
        raise PlannerError(f"map needs exactly one goal, found {len(goals)}")

    cells = tuple(line.replace(START, FREE).replace(GOAL, FREE)
                  for line in lines)
    return GridMap(cells=cells, start=starts[0], goal=goals[0], name=name)


def load_map(path: str | Path) -> GridMap:
    """Read and validate a map file."""
    source = Path(path)
    if not source.is_file():
        raise PlannerError(f"map file not found: {source}")
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise PlannerError(f"could not read {source.name}: {exc}") from exc
    return parse_map(text, name=source.stem)


def check_point(grid: GridMap, point: Point, label: str) -> Point:
    """Validate a single cell coordinate."""
    if (not isinstance(point, (tuple, list)) or len(point) != 2
            or any(isinstance(v, bool) or not isinstance(v, int)
                   for v in point)):
        raise PlannerError(f"{label} must be a (row, col) pair of integers")
    row, col = int(point[0]), int(point[1])
    if not grid.in_bounds((row, col)):
        raise PlannerError(
            f"{label} {(row, col)} is outside the {grid.rows}x{grid.cols} "
            f"grid")
    if not grid.is_free((row, col)):
        raise PlannerError(f"{label} {(row, col)} is a wall")
    return row, col


def parse_point(text: str) -> Point:
    """Parse 'row,col' into a cell coordinate."""
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(parts) != 2:
        raise PlannerError(f"point must be 'row,col', got {text!r}")
    try:
        return int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise PlannerError(
            f"point coordinates must be integers, got {text!r}") from exc


# --------------------------------------------------------------------------- #
# Movement
# --------------------------------------------------------------------------- #
def neighbours(grid: GridMap, point: Point, diagonal: bool = True,
               allow_corner_cutting: bool = False) -> list[tuple[Point, float]]:
    """Free neighbours of a cell with movement costs, in a fixed order."""
    steps = ORTHOGONAL + (DIAGONAL if diagonal else ())
    found: list[tuple[Point, float]] = []
    row, col = point
    for dr, dc in steps:
        target = (row + dr, col + dc)
        if not grid.is_free(target):
            continue
        if dr and dc and not allow_corner_cutting:
            if not (grid.is_free((row + dr, col))
                    and grid.is_free((row, col + dc))):
                continue
        found.append((target, DIAGONAL_COST if dr and dc else 1.0))
    return found


def step_allowed(grid: GridMap, start: Point, end: Point,
                 allow_corner_cutting: bool = False) -> bool:
    """True when a single 8-connected step is legal."""
    dr, dc = end[0] - start[0], end[1] - start[1]
    if max(abs(dr), abs(dc)) != 1:
        return False
    if not grid.is_free(end):
        return False
    if dr and dc and not allow_corner_cutting:
        return (grid.is_free((start[0] + dr, start[1]))
                and grid.is_free((start[0], start[1] + dc)))
    return True


def bresenham(start: Point, end: Point) -> list[Point]:
    """Every cell on the integer line from start to end, endpoints included."""
    r0, c0 = start
    r1, c1 = end
    dr, dc = abs(r1 - r0), abs(c1 - c0)
    step_r = 1 if r1 >= r0 else -1
    step_c = 1 if c1 >= c0 else -1
    error = dr - dc
    cells: list[Point] = []
    row, col = r0, c0
    while True:
        cells.append((row, col))
        if (row, col) == (r1, c1):
            return cells
        doubled = 2 * error
        if doubled > -dc:
            error -= dc
            row += step_r
        if doubled < dr:
            error += dr
            col += step_c


def line_of_sight(grid: GridMap, start: Point, end: Point,
                  allow_corner_cutting: bool = False) -> bool:
    """True when a straight 8-connected walk from start to end is legal."""
    if start == end:
        return grid.is_free(start)
    cells = bresenham(start, end)
    if any(not grid.is_free(cell) for cell in cells):
        return False
    return all(step_allowed(grid, cells[i], cells[i + 1],
                            allow_corner_cutting)
               for i in range(len(cells) - 1))


# --------------------------------------------------------------------------- #
# Costs and metrics
# --------------------------------------------------------------------------- #
def path_cost(path: list[Point] | tuple[Point, ...],
              diagonal: bool = True) -> float:
    """Sum of movement costs along a contiguous path."""
    if len(path) < 2:
        return 0.0
    total = 0.0
    for start, end in zip(path, path[1:]):
        dr, dc = abs(end[0] - start[0]), abs(end[1] - start[1])
        if max(dr, dc) != 1:
            raise PlannerError(
                f"path is not contiguous: {start} -> {end}")
        if dr and dc:
            if not diagonal:
                raise PlannerError("diagonal step in an orthogonal path")
            total += DIAGONAL_COST
        else:
            total += 1.0
    return total


def route_cost(path: list[Point] | tuple[Point, ...],
               diagonal: bool = True) -> float:
    """Cost of a waypoint route: each leg walked as a straight 8-connected line."""
    if len(path) < 2:
        return 0.0
    total = 0.0
    for start, end in zip(path, path[1:]):
        dr, dc = abs(end[0] - start[0]), abs(end[1] - start[1])
        if dr == 0 and dc == 0:
            continue
        if diagonal:
            diagonal_steps = min(dr, dc)
            orthogonal_steps = max(dr, dc) - diagonal_steps
            total += diagonal_steps * DIAGONAL_COST + orthogonal_steps
        else:
            if dr and dc:
                raise PlannerError(
                    f"leg {start} -> {end} needs a diagonal step")
            total += dr + dc
    return total


def path_turns(path: list[Point] | tuple[Point, ...]) -> int:
    """Number of direction changes along a path."""
    if len(path) < 3:
        return 0
    turns = 0
    previous = (path[1][0] - path[0][0], path[1][1] - path[0][1])
    for index in range(1, len(path) - 1):
        current = (path[index + 1][0] - path[index][0],
                   path[index + 1][1] - path[index][1])
        if current != previous:
            turns += 1
        previous = current
    return turns


def heuristic(name: str, a: Point, b: Point) -> float:
    """Admissible heuristic between two cells."""
    if name not in HEURISTICS:
        raise PlannerError(
            f"unknown heuristic {name!r} "
            f"(choose from {', '.join(HEURISTICS)})")
    dr, dc = abs(a[0] - b[0]), abs(a[1] - b[1])
    if name == "zero":
        return 0.0
    if name == "manhattan":
        return float(dr + dc)
    if name == "euclidean":
        return math.hypot(dr, dc)
    return max(dr, dc) + (DIAGONAL_COST - 1.0) * min(dr, dc)


# --------------------------------------------------------------------------- #
# Plans
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Plan:
    """A planned path plus search bookkeeping."""

    algorithm: str
    path: tuple[Point, ...]
    cost: float
    expanded: int
    heuristic: str = "-"

    @property
    def length(self) -> int:
        return len(self.path)

    @property
    def euclidean_length(self) -> float:
        return sum(math.hypot(b[0] - a[0], b[1] - a[1])
                   for a, b in zip(self.path, self.path[1:]))

    def to_dict(self) -> dict:
        return {"algorithm": self.algorithm, "heuristic": self.heuristic,
                "cost": round(self.cost, 6),
                "expanded": self.expanded,
                "steps": max(0, self.length - 1),
                "euclidean_length": round(self.euclidean_length, 6),
                "path": [list(point) for point in self.path]}


def _reconstruct(parent: dict, goal: Point) -> tuple[Point, ...]:
    path = [goal]
    seen = {goal}
    while path[-1] in parent:
        nxt = parent[path[-1]]
        if nxt in seen:
            break
        seen.add(nxt)
        path.append(nxt)
    return tuple(reversed(path))


def _densify(path: tuple[Point, ...]) -> tuple[Point, ...]:
    """Expand multi-cell straight segments into unit steps."""
    if len(path) < 2:
        return path
    cells = [path[0]]
    for start, end in zip(path, path[1:]):
        cells.extend(bresenham(start, end)[1:])
    return tuple(cells)


def astar(grid: GridMap, start: Point | None = None,
          goal: Point | None = None, diagonal: bool = True,
          heuristic_name: str | None = None,
          allow_corner_cutting: bool = False) -> Plan:
    """A* search; ``heuristic_name=None`` picks octile or manhattan."""
    start = check_point(grid, start if start is not None else grid.start,
                        "start")
    goal = check_point(grid, goal if goal is not None else grid.goal, "goal")
    if heuristic_name is None:
        heuristic_name = "octile" if diagonal else "manhattan"
    if heuristic_name not in HEURISTICS:
        raise PlannerError(
            f"unknown heuristic {heuristic_name!r} "
            f"(choose from {', '.join(HEURISTICS)})")
    if start == goal:
        return Plan("astar", (start,), 0.0, 1, heuristic_name)

    counter = 0
    open_heap: list[tuple[float, int, float, Point]] = [
        (heuristic(heuristic_name, start, goal), counter, 0.0, start)]
    best_cost = {start: 0.0}
    parent: dict[Point, Point] = {}
    expanded = 0

    while open_heap:
        _, _, cost_so_far, current = heapq.heappop(open_heap)
        if cost_so_far > best_cost.get(current, math.inf) + EPS:
            continue
        if current == goal:
            path = _reconstruct(parent, goal)
            return Plan("astar", path, path_cost(path, diagonal),
                        expanded, heuristic_name)
        expanded += 1
        for neighbour, step in neighbours(grid, current, diagonal,
                                          allow_corner_cutting):
            candidate = cost_so_far + step
            if candidate + EPS < best_cost.get(neighbour, math.inf):
                best_cost[neighbour] = candidate
                parent[neighbour] = current
                counter += 1
                heapq.heappush(
                    open_heap,
                    (candidate + heuristic(heuristic_name, neighbour, goal),
                     counter, candidate, neighbour))

    raise PlannerError(
        f"no path from {start} to {goal} "
        f"({grid.rows}x{grid.cols} grid, diagonal={diagonal})")


def dijkstra(grid: GridMap, start: Point | None = None,
             goal: Point | None = None, diagonal: bool = True,
             allow_corner_cutting: bool = False) -> Plan:
    """Uniform-cost search: A* with a zero heuristic."""
    plan = astar(grid, start, goal, diagonal=diagonal,
                 heuristic_name="zero",
                 allow_corner_cutting=allow_corner_cutting)
    return Plan("dijkstra", plan.path, plan.cost, plan.expanded, "zero")


def rrt(grid: GridMap, start: Point | None = None,
        goal: Point | None = None, seed: int = 7, step: int = 3,
        max_iters: int = 3000, goal_bias: float = 0.2,
        allow_corner_cutting: bool = False) -> Plan:
    """Seeded rapidly-exploring random tree on the grid."""
    start = check_point(grid, start if start is not None else grid.start,
                        "start")
    goal = check_point(grid, goal if goal is not None else grid.goal, "goal")
    if isinstance(step, bool) or not isinstance(step, int) or step < 1:
        raise PlannerError(f"step must be an integer >= 1, got {step!r}")
    if max_iters < 1:
        raise PlannerError(f"max_iters must be >= 1, got {max_iters}")
    if not 0.0 <= goal_bias <= 1.0:
        raise PlannerError(f"goal_bias must be in 0..1, got {goal_bias}")
    if start == goal:
        return Plan("rrt", (start,), 0.0, 1)

    rng = random.Random(seed)
    nodes: list[Point] = [start]
    parent: dict[Point, Point] = {}
    for _ in range(max_iters):
        if rng.random() < goal_bias:
            sample = goal
        else:
            sample = (rng.randrange(grid.rows), rng.randrange(grid.cols))
        if not grid.is_free(sample):
            continue
        nearest = min(nodes, key=lambda node: (
            (node[0] - sample[0]) ** 2 + (node[1] - sample[1]) ** 2,
            node[0], node[1]))
        distance = max(abs(sample[0] - nearest[0]),
                       abs(sample[1] - nearest[1]))
        if distance == 0:
            continue
        scale = min(1.0, step / distance)
        candidate = (nearest[0] + round((sample[0] - nearest[0]) * scale),
                     nearest[1] + round((sample[1] - nearest[1]) * scale))
        if candidate == nearest or not grid.is_free(candidate):
            continue
        if not line_of_sight(grid, nearest, candidate,
                             allow_corner_cutting):
            continue
        if candidate == goal:
            parent[goal] = nearest
            path = _densify(_reconstruct(parent, goal))
            return Plan("rrt", path, path_cost(path), len(nodes))
        parent[candidate] = nearest
        nodes.append(candidate)
        if (line_of_sight(grid, candidate, goal, allow_corner_cutting)
                and max(abs(candidate[0] - goal[0]),
                        abs(candidate[1] - goal[1])) <= 2 * step):
            parent[goal] = candidate
            path = _densify(_reconstruct(parent, goal))
            return Plan("rrt", path, path_cost(path), len(nodes))

    raise PlannerError(
        f"rrt did not reach {goal} from {start} in {max_iters} iteration(s)")


def find_path(grid: GridMap, algorithm: str = "astar", **kwargs) -> Plan:
    """Dispatch to one of the three planners."""
    if algorithm not in ALGORITHMS:
        raise PlannerError(
            f"unknown algorithm {algorithm!r} "
            f"(choose from {', '.join(ALGORITHMS)})")
    if algorithm == "astar":
        return astar(grid, **kwargs)
    if algorithm == "dijkstra":
        return dijkstra(grid, **kwargs)
    return rrt(grid, **kwargs)


def smooth_path(grid: GridMap, path: list[Point] | tuple[Point, ...],
                allow_corner_cutting: bool = False) -> tuple[Point, ...]:
    """Shortcut a path while keeping every segment collision-free."""
    if len(path) < 3:
        return tuple(path)
    for point in path:
        if not grid.is_free(point):
            raise PlannerError(f"path crosses a wall at {point}")
    for start, end in zip(path, path[1:]):
        if not step_allowed(grid, start, end, allow_corner_cutting):
            raise PlannerError(
                f"path is not contiguous: {start} -> {end}")

    smoothed: list[Point] = [path[0]]
    index = 0
    while index < len(path) - 1:
        farthest = index + 1
        for candidate in range(len(path) - 1, index, -1):
            if line_of_sight(grid, path[index], path[candidate],
                             allow_corner_cutting):
                farthest = candidate
                break
        smoothed.append(path[farthest])
        index = farthest
    return tuple(smoothed)


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def render_map(grid: GridMap, path: list[Point] | tuple[Point, ...] = ()
               ) -> str:
    """ASCII map with the route drawn as ``o``."""
    route: set[Point] = set()
    if path:
        route.add(path[0])
        for start, end in zip(path, path[1:]):
            route.update(bresenham(start, end))
    lines = []
    for row in range(grid.rows):
        chars = []
        for col in range(grid.cols):
            point = (row, col)
            if point == grid.start:
                chars.append(START)
            elif point == grid.goal:
                chars.append(GOAL)
            elif point in route:
                chars.append("o")
            else:
                chars.append(grid.cells[row][col])
        lines.append("".join(chars))
    return "\n".join(lines)


def render_report(plan: Plan) -> str:
    """One-block summary of a plan."""
    first = plan.path[0] if plan.path else None
    last = plan.path[-1] if plan.path else None
    return "\n".join([
        f"PLAN - {plan.algorithm}"
        + (f" ({plan.heuristic})" if plan.heuristic != "-" else ""),
        "-" * 68,
        f"  start     : {first}",
        f"  goal      : {last}",
        f"  steps     : {max(0, plan.length - 1)}",
        f"  cost      : {plan.cost:.4f}",
        f"  euclidean : {plan.euclidean_length:.4f}",
        f"  turns     : {path_turns(plan.path)}",
        f"  expanded  : {plan.expanded}",
    ])


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_MAP = Path(__file__).resolve().parent.parent / "data" / "map.txt"


def _blocked_map() -> GridMap:
    return parse_map("\n".join([
        "#####",
        "#S#G#",
        "#####",
    ]), name="blocked")


def run_demo(map_path: Path | None = None) -> int:
    """Run the bundled path-planning demo - fully offline."""
    print("=" * 68)
    print(" PATH PLANNER - offline demo")
    print(" A*, Dijkstra, RRT and line-of-sight smoothing on a text map.")
    print("=" * 68)

    source = map_path or DEMO_MAP
    if not source.is_file():
        raise PlannerError(f"bundled map not found: {source}")
    grid = load_map(source)
    print(f"\nLoaded {grid.name}: {grid.rows}x{grid.cols} cells, "
          f"{grid.free_cells()} free, start {grid.start}, goal {grid.goal}")
    print()
    print(render_map(grid))

    plans = {}
    for algorithm in ("astar", "dijkstra", "rrt"):
        plan = find_path(grid, algorithm=algorithm)
        plans[algorithm] = plan
        print()
        print(render_report(plan))

    print()
    header = (f"{'ALGO':<10}{'COST':>10}{'STEPS':>8}{'TURNS':>8}"
              f"{'EXPANDED':>10}")
    print(header)
    print("-" * len(header))
    for algorithm, plan in plans.items():
        print(f"{algorithm:<10}{plan.cost:10.4f}"
              f"{plan.length - 1:>8}{path_turns(plan.path):>8}"
              f"{plan.expanded:>10}")

    # --- cross-checks the demo asserts ------------------------------------- #
    # 1. A* and Dijkstra agree on the optimal cost
    assert abs(plans["astar"].cost - plans["dijkstra"].cost) < 1e-9, \
        "A* and Dijkstra disagree on cost"

    # 2. the heuristic does not expand more nodes than uniform cost
    assert plans["astar"].expanded <= plans["dijkstra"].expanded, \
        "A* expanded more nodes than Dijkstra"

    # 3. every path is contiguous, in bounds and collision free
    for algorithm, plan in plans.items():
        assert plan.path[0] == grid.start, f"{algorithm} misses the start"
        assert plan.path[-1] == grid.goal, f"{algorithm} misses the goal"
        for point in plan.path:
            assert grid.is_free(point), f"{algorithm} crosses a wall"
        for start, end in zip(plan.path, plan.path[1:]):
            assert step_allowed(grid, start, end), \
                f"{algorithm} takes an illegal step {start} -> {end}"
        assert abs(plan.cost - path_cost(plan.path)) < 1e-9
        assert plan.length >= 2

    # 4. smoothing keeps the endpoints, the legality and never adds cost
    raw = plans["dijkstra"].path
    smoothed = smooth_path(grid, raw)
    assert smoothed[0] == raw[0] and smoothed[-1] == raw[-1]
    assert route_cost(smoothed) <= path_cost(raw) + 1e-9
    for start, end in zip(smoothed, smoothed[1:]):
        assert line_of_sight(grid, start, end), "smoothed segment hits a wall"
    assert len(smoothed) <= len(raw)
    print(f"\nSmoothing       : {len(raw)} -> {len(smoothed)} waypoints, "
          f"cost {path_cost(raw):.4f} -> {route_cost(smoothed):.4f}")

    # 5. RRT is deterministic for a fixed seed
    again = rrt(grid, seed=7)
    assert again.path == plans["rrt"].path, "rrt is not deterministic"
    assert abs(again.cost - plans["rrt"].cost) < 1e-12

    # 6. a fully blocked map is reported, not crashed
    try:
        astar(_blocked_map())
    except PlannerError as exc:
        assert "no path" in str(exc)
    else:
        raise AssertionError("blocked map did not raise")

    # 7. an invalid map symbol is rejected
    try:
        parse_map("#S?G#")
    except PlannerError as exc:
        assert "unknown map symbol" in str(exc)
    else:
        raise AssertionError("bad symbol was accepted")

    # 8. the path is drawn back onto the map
    drawing = render_map(grid, smoothed)
    assert drawing.count("o") >= len(smoothed) - 2, "path not drawn"
    print()
    print(drawing)

    print("\nCross-checks OK: A* and Dijkstra agree on cost, A* expands "
          "fewer nodes, every path is legal and contiguous, smoothing "
          "never lengthens a path, RRT is deterministic, blocked maps "
          "and bad symbols are rejected")
    print("\nDemo completed successfully.")
    return 0
