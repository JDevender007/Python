<div align="center">

# 🗺️ Path Planner

### A\*, Dijkstra and a seeded RRT on a text occupancy grid — 8-connected movement, corner rules, line-of-sight smoothing, ASCII rendering. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Stdlib](https://img.shields.io/badge/Dependencies-Standard%20Library-blue?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

A map is a text file. `#` is a wall, `.` is free space, `S` marks the start and `G` the goal:

```text
#####################
#S#...........#.....#
#.....##.#.#..###.#.#
#...........#.......#
...
#.....#............G#
#####################
```

Given that, this project answers three questions: **is there a path, what is the cheapest one, and what does it look like?**

**Three planners.** `astar` is best-first search with an admissible heuristic (octile by default, also manhattan, euclidean or zero). `dijkstra` is the same loop with a zero heuristic, i.e. uniform-cost search — on the bundled map both return cost `27.0711`, but A\* expands **94** nodes and Dijkstra **176**. `rrt` grows a seeded rapidly-exploring random tree: it samples a cell, extends the nearest tree node toward it by up to `step` cells, and stops when a node can see the goal. Same seed, same path, every run.

**Movement has rules.** The grid is 8-connected: orthogonal steps cost `1`, diagonal steps `√2`. By default a diagonal move may not squeeze between two blocked orthogonal neighbours, so a route cannot slip through a wall corner. `--corner-cutting` relaxes that (and the bundled map's optimal cost drops accordingly). Every path is validated as contiguous and collision-free before it is reported.

**Smoothing is a separate step.** A\* returns every cell it steps through, which is correct but noisy. `smooth_path` walks the path greedily and replaces runs with the farthest endpoint that still has **line of sight** — a Bresenham walk whose cells are all free and whose every step is legal. On the bundled map that takes the route from `26` cells to `6` waypoints at exactly the same cost, because the shortcut follows the same diagonal run.

**RRT is different by nature.** It returns a feasible path, not an optimal one — cost `33.41` against A\*'s `27.07` on the bundled map — and its value is that it needs no heuristic and no expansion of the whole grid. Its tree edges are multi-cell segments, so the result is densified back into unit steps before it is measured or drawn.

The bundled map is a 15×21 maze with a guaranteed solution; the demo runs all three planners, validates every path, smooths one, re-runs RRT to prove determinism, and checks that blocked maps and bad symbols are rejected.

No network, no API keys, no images: everything is a local text file.

---

# ✨ Features

- Text map parser with strict validation (rectangular grid, known symbols, exactly one start and goal)
- 8-connected or 4-connected movement with per-step costs
- Corner-cutting rule enforced by default and toggleable
- A\* with four heuristics, Dijkstra, and seeded RRT
- Dijkstra/A\* optimality cross-check and expansion-count comparison
- Bresenham line of sight shared by smoothing and RRT
- Line-of-sight path smoothing that never lengthens a route
- Path metrics: cost, step count, turns, Euclidean length, nodes expanded
- ASCII rendering with the route drawn as `o`
- `--map`, `--algorithm`, `--heuristic`, `--start`, `--goal`, `--no-diagonal`, `--corner-cutting`, `--smooth`, `--seed`, `--step`, `--max-iters`, `--json`, `--quiet`
- Fast-fail flag validation before the map is read
- 113 passing pytest tests

---

# 📂 Folder Structure

```text
Path_Planner/
│
├── src/
│   ├── main.py     # CLI: planners, smoothing, JSON export
│   └── planner.py  # map model, movement, A*/Dijkstra/RRT, smoothing, demo
│
├── tests/
│   └── test_planner.py
│
├── data/
│   └── map.txt     # 15x21 maze, start (1,1), goal (13,19)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 22_Robotics/Path_Planner

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

No runtime dependencies — `requirements.txt` only pins pytest.

---

# ▶️ Run

```bash
# Offline demo: three planners over the bundled map, then 8 self-checks
python src/main.py --demo

# A* on the bundled map
python src/main.py --map data/map.txt

# Dijkstra plus smoothing
python src/main.py --map data/map.txt --algorithm dijkstra --smooth

# RRT with a different seed and a bigger step
python src/main.py --map data/map.txt --algorithm rrt --seed 21 --step 4

# Override the endpoints and export the plan
python src/main.py --map data/map.txt --start "1,1" --goal "13,19" \
                   --json plan.json
```

**Input:** a text file where every row has the same width and the only symbols are `#`, `.`, `S` and `G`.

**Exit codes:** `0` = success · `2` = usage, validation, missing map or no path.

---

# 🧠 How It Works

```text
map.txt ──► parse + validate ──► GridMap(cells, start, goal)
                                      │
                    ┌─────────────────┼──────────────────┐
                    ▼                 ▼                  ▼
                  A*              Dijkstra              RRT
            f = g + h          f = g              sample → nearest
            octile h           zero h             extend ≤ step
                    │                 │                  │
                    └─────────────────┼──────────────────┘
                                      ▼
                          Plan(path, cost, expanded)
                                      │
                              smooth_path (LOS)
                                      │
                              render_map / JSON
```

Movement:

```text
orthogonal step  cost 1
diagonal step    cost √2, allowed only if both orthogonal
                 neighbours are free (unless corner cutting)
```

Heuristics (admissible for 8-connected grids):

```text
octile    = max(dr, dc) + (√2 − 1) · min(dr, dc)
manhattan = dr + dc
euclidean = √(dr² + dc²)
zero      = 0            (turns A* into Dijkstra)
```

Line of sight is a Bresenham walk: every cell on the line must be free and every consecutive pair must be a legal step. Smoothing reuses exactly that predicate, so a shortcut that the smoother accepts is a shortcut the robot could drive.

---

# 🛠 Technologies

- Python 3 standard library (`heapq`, `math`, `random`, `dataclasses`, `argparse`, `json`)
- pytest

No NumPy, no image library, no game engine.

---

# 📚 Concepts Covered

- Occupancy grids and text map formats
- Breadth of search: uniform-cost vs heuristic-guided
- Admissible heuristics and why A\* stays optimal
- Priority queues with deterministic tie-breaking
- 8-connected movement costs and the corner-cutting problem
- Path reconstruction from a parent map
- Rapidly-exploring random trees, sampling bias and determinism
- Line of sight with Bresenham's algorithm
- Path smoothing / shortcutting with feasibility checks
- Path metrics: cost vs Euclidean length vs turn count
- Validation at the boundary and CLI fast-fail checks

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**113 tests passed** covering map parsing (empty, ragged rows, unknown symbols, missing/duplicate start and goal), point parsing and bounds checks, neighbour generation with and without diagonal moves and corner cutting, Bresenham and line of sight, path/route cost and turn metrics, A\* optimality and legality, Dijkstra equivalence and expansion counts, RRT determinism, path shape and error paths, smoothing legality and non-lengthening, ASCII rendering, JSON export, demo idempotency, and every CLI branch.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
