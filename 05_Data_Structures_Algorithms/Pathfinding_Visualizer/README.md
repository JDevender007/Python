<div align="center">

# 🗺️ Pathfinding Visualizer

### The legacy project put `execution_time_ms: float` inside its `SearchResult`. That one field makes the result unreproducible — the same search on the same grid returns a different object every run, so two results cannot be compared and a stored one cannot be replayed. And `Greedy Best First Search` sat in the same dropdown as BFS, Dijkstra and A*, although on the bundled grid it walks 16 steps where the shortest route is 10.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old visualizer ran five searches and reported each one like this:

```python
@dataclass(frozen=True, slots=True)
class SearchResult:
    visited_order: tuple[Node, ...]
    path: tuple[Node, ...]
    execution_time_ms: float
    found: bool

elapsed_ms = (perf_counter() - started_at) * 1_000.0
```

Four things follow.

**1 → A wall-clock field makes a result unreproducible.** `execution_time_ms`
measures the machine, not the algorithm. The same search on the same grid returns
a different `SearchResult` every run, so `result_a == result_b` can never be true,
nothing can be pinned in a test, and a stored result cannot be replayed. Worse, the
field invites the only comparison it makes possible — "A* took 0.31 ms, Dijkstra
took 0.44 ms" — on a grid so small that both numbers are noise. This module reports
**expansions** instead: an integer counting the cells a search actually removed
from its frontier. Two runs agree exactly, so the number can be compared and pinned.

**2 → Greedy best-first is in the same dropdown as the optimal three, and it is not
one of them.** It ranks the frontier by the heuristic alone and keeps no record of
how far it has travelled, so the path it returns can be longer than the shortest
one. On the bundled 6×6 grid it walks **16 steps where breadth-first walks 10**:
it hugs the top edge and the right edge because those cells look nearer to the end,
then has to cut back. The legacy result has `found: bool` and no notion of
"shortest", so five algorithms that promise different things are presented as
interchangeable.

**3 → `found=bool(path)` cannot tell "no route" from "no search".** A grid whose end
is walled off returns the same empty path as a search that never ran, and the
visualizer animates nothing. The expansion count does distinguish them: on the
sealed 2×2 grid all five searches report `found nothing` **after one expansion** —
they demonstrably ran.

**4 → Tie-breaking is part of the algorithm.** Both heaps here carry a monotonic
counter, so equal estimates are broken by insertion order and a run repeats exactly.
A heap of bare numbers leaves the order to whatever the tuple comparison does, and
two cells with the same estimate swap places for no stated reason.

| | legacy | here |
|---|---|---|
| what a result costs | `execution_time_ms: float` | `expansions: int` |
| two runs of one search | never equal | equal, and pinned in tests |
| shortest path | not a concept | `steps`, checked against BFS |
| greedy | one of five equals | reported as 6 steps longer |
| a walled-off end | an empty animation | 1 expansion, `found nothing` |
| a bad grid | an exception in the UI | `PathError` naming the line |

Standard library only: no `tkinter`, no `numpy`, no `networkx`, no network.

---

# ✨ Features

- `Cell` — row and column, ordered so output is stable; refuses a negative or
  non-integer coordinate, and refuses to step off the top or left edge
- `Grid` — rows, start, end; `neighbors` in a fixed right/down/left/up order,
  `walls`, `open_cells`, `render(path, expanded)`, and a refusal for every
  malformed grid (one row, one column, ragged, unknown character, start = end,
  start outside, start on a wall)
- `read_grid` — `S`, `E`, `#` and `.`; `;` or `//` comments; a ragged row named by
  line number; `#` is never a comment, because a row can start against the wall
- `Outcome` — algorithm, path, expanded; `found`, `steps`, `expansions`,
  `follows_edges`, `summary`, `to_dict` — and deliberately **no clock field**
- `breadth_first` — fewest steps by construction
- `depth_first` — a stack: 16 steps, and honest about it
- `dijkstra` — the same 10 steps as BFS, expanding the same 28 cells, which is the
  point of uniform costs
- `astar` — the same 10 steps in 25 expansions: the heuristic earns its keep
- `greedy` — the heuristic alone: 16 steps in 20 expansions, faster and worse
- `resolve` — `bfs` and `dfs` aliases, case and spaces ignored
- `legacy_times` / `legacy_spread` — the clock, kept only so the demo can refute it
- `has_clock` — reads `__dataclass_fields__`, so the audit's clock check has a
  negative control that does not depend on speed
- `audit` — ten named checks, each with a negative control in the suite
- `data/grid.txt` — 6×6, 7 walls, 29 open cells, 161 bytes
- CLI: `--algorithm`, `--render`, `--legacy`, `--sealed`, `--audit`, `--json`,
  `--grid`, `--quiet`, `--demo`
- 157 passing pytest tests

---

# 📂 Folder Structure

```text
Pathfinding_Visualizer/
│
├── src/
│   ├── main.py       # CLI: the table, the render, the clock, the audit, json
│   └── pathfind.py   # cells, grid, five searches, audit, demo
│
├── tests/
│   └── test_pathfind.py
│
├── data/
│   └── grid.txt      # a 6x6 trap for greedy best-first
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 05_Data_Structures_Algorithms/Pathfinding_Visualizer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: the grid, five searches, greedy's detour, the clock, the audit
python src/main.py --demo

# All five searches on the bundled grid
python src/main.py

# One search, and the grid drawn with its path
python src/main.py --algorithm greedy --render greedy
python src/main.py --algorithm astar --render astar

# The legacy field, and the grid that nothing can reach
python src/main.py --legacy
python src/main.py --sealed

# Every check, and the JSON
python src/main.py --audit
python src/main.py --json outcomes.json

# A grid of your own
python src/main.py --grid .\my_grid.txt
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a
missing grid file, a ragged or malformed grid, or an unknown algorithm name.

---

# ⚙️ How It Works

```text
read_grid(path)
  ├── ';' or '//' starts a comment -- '#' is a wall, not a comment
  ├── every row must be the same width; the failing row is named by line
  └── exactly one S and one E, or PathError

breadth_first(grid)
  ├── queue = deque([start]); seen = {start}
  ├── pop left, count the expansion, stop at the end
  └── fewest steps, by construction

dijkstra / astar
  ├── a heap of (cost, tie_break, cell) with a monotonic tie_break
  ├── a stale entry is skipped when its cost is worse than the best known
  └── astar's key is cost + manhattan, so it expands 25 cells instead of 28

greedy
  ├── a heap of (manhattan, tie_break, cell)
  ├── seen is a set: there is no cost to compare, which is the flaw
  └── 16 steps, 20 expansions -- four steps bought for six
```

Details worth knowing:

- **The clock is quarantined in `legacy_times`.** It is imported inside the
  function, so the module itself never touches a timer, and `Outcome` has no field
  that could hold one. `has_clock` reads the field names rather than the values, so
  a result is judged by its shape, not by how fast the run happened to be.
- **The demo never prints a measured number.** Printing "39 distinct values between
  180.3 and 491.8" would make the demo's own output non-deterministic — the very
  defect it is describing. It prints *that* the 40 runs disagree, and how many
  expansions two runs share.
- **`breadth_first` is the reference, and it is recomputed.** `audit` runs its own
  BFS rather than trusting the one in the list, so a `breadth` outcome that drifts
  is caught by comparing it with a fresh search.
- **Dijkstra and BFS expanding the same 28 cells is a claim, not a coincidence.**
  With every move costing one, a heap ordered by cost visits cells in distance
  order exactly as a queue does; the check will report honestly if a tie-break ever
  changes that.
- **`greedy`'s `seen` is a set, not a cost map.** That is the whole difference: no
  record of the distance already walked. It cannot revise a decision, so the first
  cell to discover a neighbour becomes its parent for good.
- **`#` is a wall, so a comment cannot start with `#`.** The bundled grid's third
  row is `#.....` — a legal row that starts against the left edge. A reader that
  treated `#` as a comment would silently delete it, so comments use `;` and `//`,
  and a test feeds a file whose first row is `#.` to prove it survives.
- **Cell coordinates cannot be negative**, so `step` refuses to walk off the top or
  left edge instead of inventing a negative cell; `neighbors` does its own
  arithmetic and only ever returns cells inside the grid.

---

# 🧪 Technologies

- Python 3 standard library: `heapq`, `itertools`, `collections.deque`,
  `dataclasses`, `pathlib`, `json`, `argparse`, `contextlib`
- pytest 9.1.1

No `tkinter`, no `numpy`, no `networkx`, no network.

---

# 📚 Concepts Covered

- A result type that cannot be compared because it holds a measurement
- Expansions as the reproducible cost of a search
- Greedy best-first versus A*: heuristic alone versus heuristic plus cost
- Optimality as a per-algorithm promise, not a property of "search"
- Uniform-cost grids, where Dijkstra and BFS do identical work
- Manhattan distance as an admissible heuristic
- Tie-breaking with a monotonic counter, so a heap run repeats exactly
- Distinguishing "no route" from "no search"
- Parsing a grid whose wall character collides with the comment character
- Audits whose negative controls do not depend on machine speed

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**157 tests passed** covering `Cell` (coordinates, ordering, equality, hash,
frozen, negative, boolean, text, two refused steps), `Grid` (rows, shape,
containment, characters, walls, open cells, neighbours and their order, iteration,
render with and without a path, and every malformed shape), `read_grid` (missing
file, both comment styles, blank lines, a `#` row that is not a comment, ragged row
with its line number, no start, no end, two starts, two ends, empty, comments only,
the bundled pins and 161 bytes), `Outcome` (`found`, `steps`, `expansions`, four
`follows_edges` cases, summary, `to_dict` keys, frozen, and no clock field at all),
`has_clock` (false for an `Outcome` and a plain object, true for
`execution_time_ms`, `elapsed_ms` and `seconds`), all five searches with pinned
steps and expansions and paths, the sealed grid, `manhattan`, `resolve` with both
aliases and three refusals, the three legacy constants, `legacy_times` and
`legacy_spread`, all ten audit checks with a negative control each, the demo, and
every CLI mode including the two exit-2 paths.

---

# 🎯 Learning Outcomes

- Explain why a wall-clock field in a result type destroys reproducibility
- Replace a measurement with a count that two runs agree on
- Tell an optimal search from a heuristic one by what it promises
- Read an expansion count as the real cost of a search
- Distinguish "the search failed" from "the search did not run"
- Write a demo whose own output does not depend on the machine

---

# 🚀 Future Improvements

- Weighted terrain, where Dijkstra and BFS stop being interchangeable
- Diagonal moves, and a heuristic that stays admissible for them
- `--trace` printing the frontier after every expansion
- A deliberately wrong heuristic behind a flag, so the optimality check has
  something to catch
- Larger grids from a generator, with the expansion ratio measured across them

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
