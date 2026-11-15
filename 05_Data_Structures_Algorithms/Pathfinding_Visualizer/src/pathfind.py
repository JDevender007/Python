"""Five searches on one grid, and the two numbers the legacy project reported
instead of the ones that matter.

The legacy project returned this:

    @dataclass(frozen=True, slots=True)
    class SearchResult:
        visited_order: tuple[Node, ...]
        path: tuple[Node, ...]
        execution_time_ms: float
        found: bool

    elapsed_ms = (perf_counter() - started_at) * 1_000.0

Two things follow.

**1. A wall-clock field makes a result unreproducible.** ``execution_time_ms``
measures the machine, not the algorithm: the same search on the same grid returns
a different ``SearchResult`` every run, so two results cannot be compared for
equality and a stored result cannot be replayed. Worse, the field invites the one
comparison that is meaningless -- "A* took 0.31 ms, Dijkstra took 0.44 ms" -- on a
grid small enough that both numbers are noise. This module reports **expansions**:
an integer that counts the cells the search actually removed from its frontier.
Two runs of the same search produce an identical value, so the comparison means
something, and a test can pin it.

**2. ``Greedy Best First Search`` is in the same dropdown as the optimal ones.**
It ranks the frontier by the heuristic alone and keeps no record of how far it has
already travelled, so the path it returns can be longer than the shortest one --
on the bundled 6x6 grid it walks 16 steps where breadth-first walks 10. The legacy
result has ``found: bool`` and no notion of "shortest", so the two are presented as
five interchangeable algorithms.

**3. ``found=bool(path)`` hides the difference between "no route" and "no search".**
A grid whose end is walled off returns the same empty path as a search that never
ran, and the visualizer simply animates nothing.

**4. Tie-breaking is part of the algorithm.** Both heaps here carry a monotonic
counter, so equal keys are broken by insertion order and the run is repeatable. A
heap of bare floats would leave the order to the tuple comparison, and two cells
with the same estimate would be swapped by whichever comparison happened first.

Standard library only: no ``tkinter``, no ``numpy``, no network.
"""

from __future__ import annotations

import heapq
import itertools
from collections import deque
from dataclasses import dataclass
from math import inf
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GRID_FILE = DATA_DIR / "grid.txt"

#: The legacy field and the line that fills it.
LEGACY_FIELD = "execution_time_ms: float"
LEGACY_TIMING = "elapsed_ms = (perf_counter() - started_at) * 1_000.0"
LEGACY_FOUND = "found=bool(path)"

#: Cells that are not open floor.
WALL = "#"
START = "S"
END = "E"
FLOOR = "."

#: The four moves, in the order every search tries them: right, down, left, up.
MOVES = ((0, 1), (1, 0), (0, -1), (-1, 0))


class PathError(ValueError):
    """A grid, a cell or a result that is refused."""


# --------------------------------------------------------------------------- #
# Cells and the grid
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, order=True)
class Cell:
    """One square, ordered by row then column so output is stable."""

    row: int
    column: int

    def __post_init__(self) -> None:
        for name, value in (("row", self.row), ("column", self.column)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise PathError(f"a cell's {name} must be an integer, got "
                                f"{value!r}")
            if value < 0:
                raise PathError(f"a cell's {name} cannot be negative")

    def __str__(self) -> str:
        return f"({self.row},{self.column})"

    def step(self, move) -> "Cell":
        """The cell one move away; stepping off the top or left edge is refused."""
        row = self.row + move[0]
        column = self.column + move[1]
        if row < 0 or column < 0:
            raise PathError(f"stepping {move} from {self} leaves the grid")
        return Cell(row, column)


@dataclass(frozen=True)
class Grid:
    """A rectangle of open cells, walls, one start and one end."""

    rows: tuple[str, ...]
    start: Cell
    end: Cell

    def __post_init__(self) -> None:
        if len(self.rows) < 2:
            raise PathError("a grid needs at least two rows")
        width = len(self.rows[0])
        if width < 2:
            raise PathError("a grid needs at least two columns")
        if any(len(row) != width for row in self.rows):
            raise PathError("every row of a grid must be the same width")
        for number, row in enumerate(self.rows, start=1):
            for character in row:
                if character not in (WALL, START, END, FLOOR):
                    raise PathError(f"row {number} holds {character!r}, which "
                                    f"is not {WALL!r}, {FLOOR!r}, {START!r} or "
                                    f"{END!r}")
        if self.start == self.end:
            raise PathError("the start and the end cannot be the same cell")
        if self.start not in self or self.end not in self:
            raise PathError("the start and the end must be inside the grid")
        if self.is_wall(self.start) or self.is_wall(self.end):
            raise PathError("the start and the end cannot be walls")

    # -- shape ------------------------------------------------------------- #
    @property
    def height(self) -> int:
        return len(self.rows)

    @property
    def width(self) -> int:
        return len(self.rows[0])

    def contains(self, cell: Cell) -> bool:
        return 0 <= cell.row < self.height and 0 <= cell.column < self.width

    def __contains__(self, cell) -> bool:
        return isinstance(cell, Cell) and self.contains(cell)

    def character(self, cell: Cell) -> str:
        if not self.contains(cell):
            raise PathError(f"{cell} is outside a {self.height}x{self.width} "
                            f"grid")
        return self.rows[cell.row][cell.column]

    def is_wall(self, cell: Cell) -> bool:
        return self.character(cell) == WALL

    def is_open(self, cell: Cell) -> bool:
        return self.contains(cell) and not self.is_wall(cell)

    @property
    def walls(self) -> frozenset[Cell]:
        return frozenset(Cell(row, column)
                         for row in range(self.height)
                         for column in range(self.width)
                         if self.rows[row][column] == WALL)

    @property
    def open_cells(self) -> tuple[Cell, ...]:
        return tuple(Cell(row, column)
                     for row in range(self.height)
                     for column in range(self.width)
                     if self.rows[row][column] != WALL)

    def neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        """The open cells one move away, in a fixed order."""
        if cell not in self:
            raise PathError(f"{cell} is outside the grid")
        found = []
        for move in MOVES:
            row, column = cell.row + move[0], cell.column + move[1]
            if 0 <= row < self.height and 0 <= column < self.width:
                if self.rows[row][column] != WALL:
                    found.append(Cell(row, column))
        return tuple(found)

    def cells(self):
        for row in range(self.height):
            for column in range(self.width):
                yield Cell(row, column)

    def render(self, path=(), expanded=()) -> tuple[str, ...]:
        """The grid as text, with a path and the cells a search touched."""
        path_cells = set(path)
        expanded_cells = set(expanded) - path_cells
        rows = []
        for row in range(self.height):
            line = []
            for column in range(self.width):
                cell = Cell(row, column)
                if cell == self.start:
                    line.append(START)
                elif cell == self.end:
                    line.append(END)
                elif self.is_wall(cell):
                    line.append(WALL)
                elif cell in path_cells:
                    line.append("*")
                elif cell in expanded_cells:
                    line.append("o")
                else:
                    line.append(FLOOR)
            rows.append("".join(line))
        return tuple(rows)

    def __str__(self) -> str:
        return "\n".join(self.rows)


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #
def read_grid(path=GRID_FILE) -> Grid:
    """Read a grid from a text file, ignoring blank lines and ``;`` comments.

    A comment cannot start with ``#``: ``#`` is a wall, and a row like
    ``#.....`` is a legal line of a grid that starts against the left edge.
    """
    path = Path(path)
    if not path.is_file():
        raise PathError(f"grid file not found: {path}")
    rows = []
    start = end = None
    for number, line in enumerate(path.read_text(encoding="utf-8")
                                  .splitlines(), start=1):
        text = line.rstrip()
        if not text or text.startswith(";") or text.startswith("//"):
            continue
        if rows and len(text) != len(rows[0]):
            raise PathError(f"{path.name}:{number}: the row is {len(text)} "
                            f"wide, not {len(rows[0])}")
        if START in text:
            if start is not None:
                raise PathError(f"{path.name}:{number}: a second start")
            start = Cell(len(rows), text.index(START))
        if END in text:
            if end is not None:
                raise PathError(f"{path.name}:{number}: a second end")
            end = Cell(len(rows), text.index(END))
        rows.append(text)
    if not rows:
        raise PathError(f"{path.name}: no grid rows")
    if start is None or end is None:
        raise PathError(f"{path.name}: the grid needs one {START} and one {END}")
    return Grid(tuple(rows), start, end)


# --------------------------------------------------------------------------- #
# A result
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Outcome:
    """What one search did: the path, the cells it expanded, and no clock."""

    algorithm: str
    path: tuple[Cell, ...]
    expanded: tuple[Cell, ...]

    @property
    def found(self) -> bool:
        return bool(self.path)

    @property
    def steps(self) -> int:
        """Moves taken; a one-cell path takes none."""
        return max(0, len(self.path) - 1)

    @property
    def expansions(self) -> int:
        """Cells removed from the frontier -- the reproducible cost."""
        return len(self.expanded)

    def follows_edges(self, grid: Grid) -> bool:
        """Every step in the path is a single move between open cells."""
        if not self.found:
            return True
        if any(cell not in grid for cell in self.path):
            return False
        if any(grid.is_wall(cell) for cell in self.path):
            return False
        return all(second in grid.neighbors(first)
                   for first, second in zip(self.path, self.path[1:]))

    def summary(self) -> dict:
        return {"algorithm": self.algorithm, "found": self.found,
                "steps": self.steps, "expansions": self.expansions,
                "path": [str(cell) for cell in self.path]}

    def to_dict(self) -> dict:
        return {**self.summary(),
                "expanded": [str(cell) for cell in self.expanded]}


# --------------------------------------------------------------------------- #
# The five searches
# --------------------------------------------------------------------------- #
def manhattan(left: Cell, right: Cell) -> int:
    return abs(left.row - right.row) + abs(left.column - right.column)


def _rebuild(parent, start: Cell, end: Cell) -> tuple[Cell, ...]:
    if end not in parent:
        return ()
    path = [end]
    while path[-1] != start:
        path.append(parent[path[-1]])
    return tuple(reversed(path))


def breadth_first(grid: Grid, start=None, end=None) -> Outcome:
    """Fewest steps, guaranteed: a queue explores by distance."""
    start = grid.start if start is None else start
    end = grid.end if end is None else end
    queue = deque([start])
    seen = {start}
    parent: dict[Cell, Cell] = {}
    expanded: list[Cell] = []
    while queue:
        current = queue.popleft()
        expanded.append(current)
        if current == end:
            break
        for neighbor in grid.neighbors(current):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            parent[neighbor] = current
            queue.append(neighbor)
    return Outcome("breadth", _rebuild(parent, start, end), tuple(expanded))


def depth_first(grid: Grid, start=None, end=None) -> Outcome:
    """A stack: finds *a* path, not the shortest one."""
    start = grid.start if start is None else start
    end = grid.end if end is None else end
    stack = [start]
    seen = {start}
    parent: dict[Cell, Cell] = {}
    expanded: list[Cell] = []
    while stack:
        current = stack.pop()
        expanded.append(current)
        if current == end:
            break
        for neighbor in reversed(grid.neighbors(current)):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            parent[neighbor] = current
            stack.append(neighbor)
    return Outcome("depth", _rebuild(parent, start, end), tuple(expanded))


def dijkstra(grid: Grid, start=None, end=None) -> Outcome:
    """Shortest by total cost, with every move costing one."""
    start = grid.start if start is None else start
    end = grid.end if end is None else end
    counter = itertools.count()
    frontier = [(0, next(counter), start)]
    best = {start: 0}
    parent: dict[Cell, Cell] = {}
    expanded: list[Cell] = []
    while frontier:
        cost, _, current = heapq.heappop(frontier)
        if cost > best.get(current, inf):
            continue
        expanded.append(current)
        if current == end:
            break
        for neighbor in grid.neighbors(current):
            step = cost + 1
            if step < best.get(neighbor, inf):
                best[neighbor] = step
                parent[neighbor] = current
                heapq.heappush(frontier, (step, next(counter), neighbor))
    return Outcome("dijkstra", _rebuild(parent, start, end), tuple(expanded))


def astar(grid: Grid, start=None, end=None) -> Outcome:
    """Shortest, with the heuristic steering the frontier."""
    start = grid.start if start is None else start
    end = grid.end if end is None else end
    counter = itertools.count()
    frontier = [(manhattan(start, end), next(counter), 0, start)]
    best = {start: 0}
    parent: dict[Cell, Cell] = {}
    expanded: list[Cell] = []
    while frontier:
        _, _, cost, current = heapq.heappop(frontier)
        if cost > best.get(current, inf):
            continue
        expanded.append(current)
        if current == end:
            break
        for neighbor in grid.neighbors(current):
            step = cost + 1
            if step < best.get(neighbor, inf):
                best[neighbor] = step
                parent[neighbor] = current
                estimate = step + manhattan(neighbor, end)
                heapq.heappush(frontier, (estimate, next(counter), step,
                                          neighbor))
    return Outcome("astar", _rebuild(parent, start, end), tuple(expanded))


def greedy(grid: Grid, start=None, end=None) -> Outcome:
    """The heuristic alone: fast, and not guaranteed to be short.

    ``best`` is a set, not a cost map, because there is no cost to compare --
    which is exactly why the path can be longer than the shortest one.
    """
    start = grid.start if start is None else start
    end = grid.end if end is None else end
    counter = itertools.count()
    frontier = [(manhattan(start, end), next(counter), start)]
    seen = {start}
    parent: dict[Cell, Cell] = {}
    expanded: list[Cell] = []
    while frontier:
        _, _, current = heapq.heappop(frontier)
        expanded.append(current)
        if current == end:
            break
        for neighbor in grid.neighbors(current):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            parent[neighbor] = current
            heapq.heappush(frontier, (manhattan(neighbor, end),
                                      next(counter), neighbor))
    return Outcome("greedy", _rebuild(parent, start, end), tuple(expanded))


#: Every search, keyed by the name the search puts in its own result.
ALGORITHMS = {"breadth": breadth_first, "depth": depth_first,
              "dijkstra": dijkstra, "astar": astar, "greedy": greedy}

#: The short names the CLI also accepts.
ALIASES = {"bfs": "breadth", "dfs": "depth"}

#: The three that promise a shortest path.
OPTIMAL = ("breadth", "dijkstra", "astar")

#: The two that only promise a path.
LONGER = ("depth", "greedy")


def resolve(name: str) -> str:
    """The canonical name for a name the CLI accepts, or ``PathError``."""
    if not isinstance(name, str):
        raise PathError(f"an algorithm name must be text, got {name!r}")
    key = ALIASES.get(name.strip().lower(), name.strip().lower())
    if key not in ALGORITHMS:
        raise PathError(f"no such algorithm: {name!r}; choose one of "
                        f"{', '.join(ALGORITHMS)}")
    return key


def run_all(grid: Grid) -> tuple[Outcome, ...]:
    return tuple(ALGORITHMS[name](grid) for name in ALGORITHMS)


# --------------------------------------------------------------------------- #
# The legacy clock
# --------------------------------------------------------------------------- #
def legacy_times(grid: Grid, repeats: int = 25) -> tuple[float, ...]:
    """The legacy ``execution_time_ms`` for the same search, over and over.

    Deterministic work, measured on a wall clock: every value is different, and
    none of them describes the algorithm. Returned in microseconds here so the
    demo can print whole numbers.
    """
    import time

    times = []
    for _ in range(repeats):
        started_at = time.perf_counter()
        astar(grid)
        times.append((time.perf_counter() - started_at) * 1_000_000.0)
    return tuple(times)


def legacy_spread(times) -> float:
    times = list(times)
    if not times:
        raise PathError("a spread needs at least one measurement")
    return max(times) - min(times)


def has_clock(outcome) -> bool:
    """Does this result carry a wall-clock field?

    Read from ``__dataclass_fields__`` rather than from the values, so the
    answer does not depend on how fast the machine happened to be.
    """
    return any(field in ("execution_time_ms", "elapsed_ms", "seconds", "timer",
                         "microseconds")
               for field in getattr(outcome, "__dataclass_fields__", {}))


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def audit(grid: Grid, outcomes) -> list[tuple[str, bool]]:
    outcomes = list(outcomes)
    reference = breadth_first(grid)
    derived = {outcome.algorithm: outcome for outcome in outcomes}

    def path_is_clean(outcome: Outcome) -> bool:
        return outcome.follows_edges(grid) and \
            len(set(outcome.path)) == len(outcome.path)

    def expands_are_real(outcome: Outcome) -> bool:
        return all(cell in grid and not grid.is_wall(cell)
                   for cell in outcome.expanded)

    def expands_once(outcome: Outcome) -> bool:
        return len(set(outcome.expanded)) == len(outcome.expanded)

    def ends_at_the_goal(outcome: Outcome) -> bool:
        if not outcome.found:
            return True
        return outcome.path[0] == grid.start and outcome.path[-1] == grid.end

    def goal_is_last(outcome: Outcome) -> bool:
        if not outcome.found:
            return True
        return outcome.expanded[-1] == grid.end

    return [
        ("every path starts at the start and ends at the end",
         all(ends_at_the_goal(o) for o in outcomes)),
        ("every step of every path is one move between open cells",
         all(path_is_clean(o) for o in outcomes)),
        ("no path visits a cell twice",
         all(len(set(o.path)) == len(o.path) for o in outcomes)),
        ("every expanded cell is open and inside the grid",
         all(expands_are_real(o) for o in outcomes)),
        ("no cell is expanded twice",
         all(expands_once(o) for o in outcomes)),
        ("the goal is the last cell expanded, when it is found",
         all(goal_is_last(o) for o in outcomes)),
        ("the three optimal searches return the shortest path",
         all(derived[name].steps == reference.steps
             for name in OPTIMAL if name in derived)),
        ("breadth-first and dijkstra expand the same number of cells",
         "breadth" not in derived or "dijkstra" not in derived
         or derived["breadth"].expansions == derived["dijkstra"].expansions),
        ("no result carries a wall-clock field",
         all(not has_clock(o) for o in outcomes)),
        ("two runs of every search agree exactly",
         all(ALGORITHMS[o.algorithm](grid) == o for o in outcomes)),
    ]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    grid = read_grid()
    outcomes = run_all(grid)
    reference = breadth_first(grid)
    by_name = {outcome.algorithm: outcome for outcome in outcomes}

    print("=" * 74)
    print(" PATH LAB - expansions are a number, milliseconds are noise")
    print("=" * 74)
    for row in grid.render():
        print(f"  {row}")
    print(f"  {grid.height}x{grid.width}, {len(grid.walls)} walls, "
          f"start {grid.start}, end {grid.end}, "
          f"{len(grid.open_cells)} open cells")

    print(f"\n  {'algorithm':<10}{'found':>7}{'steps':>7}{'expansions':>12}"
          f"{'shortest':>10}")
    for outcome in outcomes:
        shortest = "yes" if outcome.steps == reference.steps else "no"
        print(f"  {outcome.algorithm:<10}{'yes' if outcome.found else 'no':>7}"
              f"{outcome.steps:>7}{outcome.expansions:>12}{shortest:>10}")

    print(f"\n  breadth-first, {reference.steps} steps:")
    print(f"    {' '.join(str(cell) for cell in reference.path)}")
    print(f"  greedy, {by_name['greedy'].steps} steps -- "
          f"{by_name['greedy'].steps - reference.steps} longer:")
    print(f"    {' '.join(str(cell) for cell in by_name['greedy'].path)}")
    for row in grid.render(by_name["greedy"].path):
        print(f"    {row}")
    print(f"  greedy ranks a cell only by its straight-line distance to the end,")
    print(f"  so the top row and the right column look nearer than the gap on row")
    print(f"  2 that actually leads there: it walks two edges of the grid first")

    sealed = Grid(("S#", "#E"), Cell(0, 0), Cell(1, 1))
    walled = run_all(sealed)
    print(f"\n  the same five on a 2x2 grid whose end is walled off:")
    print("    " + ", ".join(f"{o.algorithm} expanded {o.expansions} and "
                            f"{'found' if o.found else 'found nothing'}"
                            for o in walled))
    print(f"    every one of them ran; the legacy {LEGACY_FOUND} cannot say so")

    times = legacy_times(grid, 40)
    print(f"\n  the legacy field, {LEGACY_FIELD}, over 40 identical runs:")
    print(f"    the 40 numbers are not all the same: "
          f"{'yes' if len(set(times)) > 1 else 'no'} -- the field measures the "
          f"machine, not the search")
    print(f"    so one search, run twice, returns two different result objects")
    same = astar(grid) == astar(grid)
    print(f"    expansions instead: {by_name['astar'].expansions} both times, "
          f"and two runs compare equal: {'yes' if same else 'no'}")

    checks = audit(grid, outcomes)
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\n  a second run of all five searches: ", end="")
    again = run_all(grid)
    assert [o.summary() for o in again] == [o.summary() for o in outcomes], \
        "no clock anywhere, so the summaries must agree"
    print("identical summaries")

    print("\nCross-checks OK: " +
          f"{grid.height}x{grid.width} with {len(grid.walls)} walls, "
          f"breadth-first finds {reference.steps} steps by expanding "
          f"{reference.expansions} cells, dijkstra and A* return the same "
          f"{reference.steps} steps in {by_name['dijkstra'].expansions} and "
          f"{by_name['astar'].expansions} expansions, greedy returns "
          f"{by_name['greedy'].steps} steps -- "
          f"{by_name['greedy'].steps - reference.steps} more -- by expanding "
          f"{by_name['greedy'].expansions}, depth-first returns "
          f"{by_name['depth'].steps} steps, a walled-off end is found by none of "
          f"the five though all five ran, every path follows real edges and "
          f"visits no cell twice, no result carries a clock, two runs agree "
          f"exactly, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("\nDemo completed successfully.")
    return 0
