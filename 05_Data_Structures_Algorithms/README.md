<div align="center">

# 📚 Data Structures & Algorithms

### Five projects that each looked like "run an algorithm and animate it" — and each one turned out to be a question about *cost*. What counts as a swap if a merge never swaps? Is `execution_time_ms` a property of the search or of the machine? Is `operations_performed` a history? When a graph search recurses, what happens at the recursion limit? The rebuild keeps each defect executable, then removes the reason it was possible.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Each of these five projects began as a `tkinter` visualizer. They all run on the bundled data exactly as the original does, and every one of them reports a number that is wrong the moment the input is not the video's input — and the failure is never a typo. It is the definition of what was being counted.

**The lesson of each project is different, on purpose.** Five variations on `time.perf_counter()` would teach nothing; five different ways an algorithm's cost is misreported teach the subject.

- **Sorting_Visualizer** — a *write* is not a *swap*. The legacy animation incremented `swaps` every time it assigned into the list, so merge sort reported 44 swaps while performing zero exchanges of two elements, and quick sort reported 36 for a run that only ever moves values through a pivot. The rebuild counts **comparisons and writes** separately, and derives the real exchange count from the permutation — 32 inversions for the bundled 12 values — so the column and the array agree. Pinned: bubble 65 comparisons / 64 writes, insertion 41 / 41, selection 66 / 18, merge 31 / 44, quick 36 / 24, heap 50 / 64.
- **Binary_Search_Visualizer** — a *comparison* is the cost, and "not found" is a result. The legacy linear scan was drawn as if it were the binary one, so 23 at index 11 looked like 11 steps instead of 2. The rebuild reports comparisons for both searches side by side (binary 47 in total, linear 132), shows that an absent 22 costs 4 comparisons against a 12-step scan, keeps the three `13`s at indices 6..8 with their own bounds (5, 5), and refuses to call "not found" an error.
- **Graph_Traversal_Visualizer** — *recursion is a stack, and the stack has a limit*. The legacy DFS called itself, so a chain longer than `sys.getrecursionlimit()` raised `RecursionError` mid-animation. The rebuild replaces it with an explicit stack that produces the **same visit order and the same distances** as the recursive version on the bundled graph, then runs a chain derived from the live limit (`recursion_limit() + 500`) that the recursive form cannot survive. BFS reaches `C` in 1 step where DFS needs 3 — same graph, different question.
- **Pathfinding_Visualizer** — a *wall clock makes a result unreproducible*. The legacy `SearchResult` carried `execution_time_ms: float`, so the same search on the same grid returned a different object every run and two results could never be compared or replayed. The rebuild reports **expansions**, and reports greedy best-first honestly: on the bundled 6×6 grid it walks 16 steps where the shortest route is 10, and a grid whose end is walled off still shows all five searches running (1 expansion each) instead of an empty animation.
- **Stack_Queue_Simulator** — *undo is a second stack, and a counter is not a history*. The legacy theory panel advertised "undo/redo systems" while its eleven callbacks undid nothing, and `self.operations_performed += 1` appeared at two sites — success and failure alike — so a rejected push counted as work done. The rebuild keeps a history of reversible steps and a future of replayed ones, counts `applied`, `refused` and `reads` separately, and reverses every mutation including the awkward ones: a heap push is undone by removing *that exact entry*, a dequeue by `add_front`, a clear item by item.

**Every count is exact and every claim is checkable.** Comparisons, writes, expansions and steps are integers, each demo prints the number it derived, and each project's `audit()`/`problems()` re-derives the result from the data instead of restating the summary it just printed.

Standard library only: no `tkinter`, no `numpy`, no `networkx`, no `matplotlib`, no network, no API keys, no downloads.

---

# 🎯 Learning Objectives

- Count an algorithm's cost in the unit that algorithm actually moves: comparisons, writes, expansions, steps
- Tell an exchange from a write, and derive it from the permutation rather than trusting a counter
- Distinguish "the search found nothing" from "the search did not run"
- Replace a wall-clock measurement with an integer two runs agree on
- Replace recursion with an explicit stack without changing the traversal's order
- Derive environment-dependent sizes (recursion limit) instead of hard-coding them
- Separate what a structure can do from what it can reverse — undo lives in a second structure
- Keep three counters that mean three different things: applied, refused, read
- Report a heuristic search against the optimal one it shares a menu with
- Write an `audit()` that returns every check, then force each one to fail
- Keep the original source as an executable constant so a defect is asserted, not described

---

# 📂 Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Sorting_Visualizer | Comparisons and writes counted separately; 32 inversions; merge sort 0 exchanges, 44 writes. | 175 | ✅
02 | Binary_Search_Visualizer | Comparisons as the cost: 23 in 2 versus linear's 12; absent 22 in 4; duplicates at 6..8. | 139 | ✅
03 | Graph_Traversal_Visualizer | Iterative DFS matching the recursive order and distances, then a chain past the recursion limit. | 141 | ✅
04 | Pathfinding_Visualizer | Expansions instead of `execution_time_ms`; greedy 16 steps against breadth-first's 10. | 157 | ✅
05 | Stack_Queue_Simulator | Undo and redo as two stacks of steps; applied/refused/reads counters; 11 callbacks, 0 undos. | 164 | ✅

**Total: 776 tests.**

---

# 💡 Concepts Covered

- Cost models: comparisons, writes, expansions, steps, and when a timer is not one of them
- Stable counting: an exchange derived from the permutation, not from an assignment
- Binary search bounds, absent keys, and duplicate runs
- Graph traversal orders: BFS queue, DFS stack, and the naive order that is neither
- Recursion as an implicit stack, and `RecursionError` as a real limit
- Priority queues with a monotonic tie-break, so a run repeats exactly
- Optimal versus merely successful: BFS, Dijkstra and A* against greedy best-first
- Heuristics: Manhattan distance, admissibility, and what greedy gives up
- Undo/redo as two stacks of reversible steps; redo invalidation on a new branch
- Inverse operations for structures that only expose one end
- Bookkeeping that must add up: `undoable + redoable + discarded == applied`
- Audits whose negative controls plant the defect where the check actually looks

---

# 📁 Repository Structure

```text
05_Data_Structures_Algorithms/
│
├── Sorting_Visualizer/
│   ├── src/    sorts.py, main.py
│   ├── tests/  test_sorts.py
│   └── data/   values.txt
│
├── Binary_Search_Visualizer/
│   ├── src/    search.py, main.py
│   ├── tests/  test_search.py
│   └── data/   numbers.txt
│
├── Graph_Traversal_Visualizer/
│   ├── src/    traversal.py, main.py
│   ├── tests/  test_traversal.py
│   └── data/   graph.txt
│
├── Pathfinding_Visualizer/
│   ├── src/    pathfind.py, main.py
│   ├── tests/  test_pathfind.py
│   └── data/   grid.txt
│
└── Stack_Queue_Simulator/
    ├── src/    structures.py, main.py
    ├── tests/  test_structures.py
    └── data/   session.txt
```

Each project has the same shape: all logic in one library module, a thin `main.py`
argparse CLI, a `tests/` suite, deterministic data in `data/`, a pinned
`requirements.txt`, a `.gitignore`, and a `README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 05_Data_Structures_Algorithms/Sorting_Visualizer

python src/main.py --demo          # offline, deterministic, exit 0
python src/main.py                 # the same work, printed as a table
python src/main.py --audit         # every check with PASS/FAIL
python -m pytest tests -q          # the suite
```

Every project supports `--demo`, `--quiet` with `--demo` (prints nothing), `--audit`,
`--json <path>`, and a `--` flag of its own (`--algorithm`, `--target`, `--source`,
`--grid`, `--session`). Nothing touches the network, no API key is read, and no file
is downloaded: each demo runs on the bundled data and finishes in under two seconds.

---

# 🎯 Learning Outcomes

This category helps you understand:

- What an algorithm's cost actually is, and which unit measures it
- Why a measured duration cannot be a field of a comparable result
- How binary search's bound narrows, and what "not found" costs
- How a queue and a stack produce two different traversals of one graph
- Why recursion fails before a stack does, and how to prove it with a derived limit
- When a heuristic search is fast and wrong, and how to report that honestly
- How undo is built out of a second structure rather than out of `pop`
- Why "operations performed" is not the same number as "changes applied"
- How to write an audit whose every check has a negative control
- How to make a demonstration reproducible byte for byte

---

# 📊 Algorithms Included

Searching — Binary Search, Linear Search
Sorting — Bubble, Insertion, Selection, Merge, Quick, Heap
Graph — Breadth-First Search, Depth-First Search
Pathfinding — BFS, Dijkstra, A\*, Greedy Best-First
Structures — Stack, Queue, Deque, Binary Heap, Grid, Adjacency List

---

# 📈 Future Improvements

- Weighted terrain and dialects of A\*, so admissibility can be tested rather than assumed
- Timsort and an adaptive sort, whose comparison counts depend on existing runs
- A tree visualizer (AVL, red-black, trie) built on the same audit harness
- Snapshot-based undo behind a flag, contrasted with step-based undo
- Larger generated inputs, with the comparison and expansion ratios measured across them

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes with a clear message.
4. Push the branch.
5. Open a Pull Request.

---

# 👨‍💻 Author

**Devender J**

Python Developer | Data Analytics Enthusiast | AI & Machine Learning Learner

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
