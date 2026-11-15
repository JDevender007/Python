<div align="center">

# 🕸️ Graph Traversal Visualizer

### The legacy project walked the graph with `yield from walk(neighbor)`. On the demo graph it is perfect. On a 1,000-node path it raises `RecursionError` — because the walk spends one interpreter stack frame per node, and the default limit is 1,000. That budget appears nowhere in the graph, in the docstring, or in the complexity table. And when the recursion was replaced with a stack, the order silently changed, because marking a node when it is **pushed** is not the same as marking it when it is **popped**.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old visualizer animated a search over a small drawn graph:

```python
def walk(current):
    for neighbor in graph.neighbors(current):
        if neighbor in visited:
            continue
        visited.add(neighbor)
        yield ...                       # one animation frame
        yield from walk(neighbor)

yield from walk(start_node)
```

Four things follow.

**1 → An algorithm's step budget is part of its interface.** "DFS needs `O(V + E)`
time" says nothing about `O(depth)` *stack*. The iterative version here keeps its
own stack on the heap, so a chain longer than the interpreter's limit is a normal
input, and the depth it reached is a number in the result rather than a crash.

**2 → An explicit stack is not a drop-in replacement for recursion: when you mark
matters.** Recursion has one frame per node and can mark on descent. A loop that
pushes every neighbour at once must mark on push — or it would push a node many
times — and marking on push changes which route reaches a node first. The faithful
rewrite here marks on **pop**, lets the stack hold a node twice, and pushes
neighbours in reverse so the first neighbour listed is taken first. Order *and*
distances then match the recursive walk exactly; the naive version visits the same
nodes in a different order and builds a different tree.

**3 → Breadth-first and depth-first are the same loop with a different end.** A
deque popped from the left is a queue; popped from the right it is a stack. The
distance column makes the difference legible: BFS's distances never decrease, DFS's
do, and the same node can be 1 hop away or 3 depending on which one you asked.

**4 → "Visited" and "discovered" are different words.** Marking on push is what
keeps BFS from re-queueing a cycle, and it also means visit order *is* discovery
order. Both facts are checked here rather than assumed, and the parent recorded is
the one that was on top of the stack when the node was visited — not whichever
neighbour happened to push it first.

| | legacy | here |
|---|---|---|
| DFS implementation | `yield from walk(neighbor)` | an explicit stack of `(node, parent)` |
| a chain longer than the limit | `RecursionError` | 1500 nodes, depth 1499 |
| DFS order | recursion's | recursion's, pinned exactly |
| distances | the recursion's tree | the same tree, checked against its own paths |
| a naive stack rewrite | looks equivalent | different order, same set — and the check says so |
| "reached every node" | assumed | checked against a union-find component |
| a miss | an empty animation | `GraphError` naming the node |

Standard library only: no `tkinter`, no `networkx`, no network.

---

# ✨ Features

- `Graph` — undirected, adjacency kept sorted so traversal order comes from the
  data rather than from the order a file listed its edges; refuses a self-edge and
  a blank name
- `Visit` — node, visit order, distance from the start; refused if order < 1
- `Traversal` — kind, start, visits, parent map; `order`, `distances`, `depth`,
  `path_to`, `summary`, `to_dict`
- `breadth_first` — a deque, marked on push
- `depth_first` — a stack marked on pop, carrying `(node, parent)`; reproduces
  recursion's order **and** distances
- `depth_first_naive` — the same stack marked on push: same set, different order
- `legacy_recursive_dfs` — the recursion, executable, and it does raise
- `components` / `component_of` / `edge_pairs` — components from a BFS, and from a
  union-find that shares no code with it, so the two check each other
- `chain(n)` — the graph that breaks a recursive walk
- `read_graph` — `left-right` lines, comments skipped, a bad line named by number
- `audit` — nine named checks; `audit_orders` — four more, comparing three walks
- `data/graph.txt` — 8 nodes, 7 edges, two components, 28 bytes
- CLI: `--start`, `--bfs`, `--dfs`, `--naive`, `--legacy`, `--components`,
  `--path`, `--chain`, `--audit`, `--json`, `--graph`, `--quiet`, `--demo`
- 141 passing pytest tests

---

# 📂 Folder Structure

```text
Graph_Traversal_Visualizer/
│
├── src/
│   ├── main.py       # CLI: the table, paths, components, legacy, audit, json
│   └── traversal.py  # graph, traversals, components, audit, demo
│
├── tests/
│   └── test_traversal.py
│
├── data/
│   └── graph.txt     # A-B A-C B-D C-D D-E C-F G-H
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 05_Data_Structures_Algorithms/Graph_Traversal_Visualizer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: both orders, the naive stack, the chain, the audit
python src/main.py --demo

# The four traversals side by side
python src/main.py
python src/main.py --naive

# One traversal, one question
python src/main.py --bfs
python src/main.py --dfs --path F
python src/main.py --components

# The recursion's budget
python src/main.py --legacy

# Every check, and the JSON
python src/main.py --audit
python src/main.py --json traversals.json

# A made graph, or a chain
python src/main.py --chain 5
python src/main.py --graph .\my_graph.txt --start X
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a
missing graph file, a malformed edge line, an unknown start node, or a chain of
length 0.

---

# ⚙️ How It Works

```text
Graph(edges)
  ├── adjacency: node -> sorted set of neighbours
  ├── add_edge refuses a self-edge and a blank name
  └── edge_count = half the sum of degrees (each edge is stored twice)

breadth_first(graph, start)
  ├── queue = deque([start]);   seen = {start}
  ├── pop left, record the visit, push unseen neighbours
  └── distances never decrease: the first time a node is seen is the shortest

depth_first(graph, start)
  ├── stack = [(start, None)];  seen = {}
  ├── pop, skip if already seen, otherwise record parent and depth
  └── push neighbours in reverse order, each with its parent

legacy_recursive_dfs(graph, start)
  └── walk(current) -> walk(neighbour)      one frame per node, and it shows
```

Details worth knowing:

- **The stack entry carries the parent.** With `parent.setdefault(neighbour,
  current)` the recorded parent is the first node that *pushed* a neighbour, which
  need not be the node that later *visited* it. Carrying `(node, parent)` makes the
  tree the one the walk actually took, so `path_to` and `distances` agree with the
  recursion instead of with a shorter path nobody walked.
- **Pushing in reverse is not cosmetic.** `stack.append` in a loop pushes the last
  neighbour last, so it is popped first. Recursion takes the first neighbour first;
  `reversed` is the one word that makes the loop agree with it.
- **A node may be on the stack twice.** Marking on pop is what allows that, and
  the skip at the top of the loop is what keeps the visit unique. Both are needed;
  either alone changes the order or the visit count.
- **`component_of` shares no code with `breadth_first`.** A union-find over the
  edges is the independent calculation, so "BFS reached exactly its component" is
  checked against something other than another BFS.
- **The chain length comes from the live limit.** `chain(recursion_limit() + 500)`
  is longer than the budget by construction, so the demonstration is the same on an
  interpreter whose limit is 1,000 and one where a test framework raised it to
  3,000.
- **Every distance is checked against its own path.** `distances_match_paths`
  recomputes `len(path_to(node)) - 1`, so a distance column that drifted from the
  tree is caught even when the order is right.

---

# 🧪 Technologies

- Python 3 standard library: `collections.deque`, `dataclasses`, `pathlib`, `sys`,
  `json`, `argparse`, `contextlib`
- pytest 9.1.1

No `tkinter`, no `networkx`, no `matplotlib`, no network.

---

# 📚 Concepts Covered

- Recursion depth as an unwritten precondition on an algorithm
- An explicit stack, and the two places a node can be marked
- Mark-on-push versus mark-on-pop: order, duplicate entries and tree shape
- `reversed` as the operation that makes a loop match a recursive call order
- Queue versus stack: one loop, two ends
- BFS distances as shortest hops, and why they never decrease
- Connected components, computed twice by independent means
- Union-find as a cross-check rather than a convenience
- Traversal trees: parent links, path reconstruction, and distance verification
- Audits that re-derive a result instead of restating it

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**141 tests passed** covering `Graph` (blank and non-text names, self-edges,
spaces around a name, duplicate edges, sorted neighbours, sorted nodes, unknown
neighbours, degree, iteration, `__str__`), `Visit` (order and distance rules,
frozen), `Traversal` (empty refused, order, distances, depth, iteration, summary,
parents, frozen), `breadth_first` (pinned order and distances, non-decreasing
distances, one component only, a single node, shortest hops, paths, three bad
starts), `depth_first` (pinned order, pinned distances, identical to recursion,
the naive order, the same set, two different paths to `F`, the distance drop, a
5-node chain, a 1500-node chain, bad start), `legacy_recursive_dfs` (pinned lines,
the live limit, a short chain survives, a chain past the limit raises, the
iterative one does not), `components` / `component_of` / `edge_pairs`,
`chain` (1, 5, ends, middle, 0 and negative refused), `read_graph` (missing file,
comments, spaces, no dash, no left side, no right side, the offending line, empty,
the bundled pins and 28 bytes), all nine audit checks with a negative control each,
all four order checks with a negative control each, the demo, and every CLI mode.

---

# 🎯 Learning Outcomes

- Recognise a recursion budget that is not in the graph's data
- Replace recursion with a stack without changing the answer
- Explain why marking on push and marking on pop are different algorithms
- Verify a traversal tree through its paths, not through its order
- Cross-check one traversal with a second, unrelated calculation
- Write a demonstration that stays true when the interpreter's limits change

---

# 🚀 Future Improvements

- Iterative deepening, to show the budget traded for repeated work
- Topological order, and a cycle detector that names the cycle
- Weighted edges and Dijkstra, so "shortest" means distance rather than hops
- A `--trace` mode that prints the frontier after every step
- A deliberately wrong implementation behind a flag, so the audit has something to catch

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
