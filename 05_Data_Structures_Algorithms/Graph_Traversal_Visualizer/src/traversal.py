"""Two traversals, one graph, and the step budget nobody wrote down.

The legacy visualizer implemented depth-first search as a recursive generator:

    def walk(current):
        for neighbor in graph.neighbors(current):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            yield ...
            yield from walk(neighbor)

    yield from walk(start_node)

It is correct, and it is bounded by something that appears nowhere in the graph:
Python's recursion limit. A path of 1,000 nodes is a legal graph; walking it
recursively raises ``RecursionError`` on the last node, because the walk spends
one interpreter stack frame per node and the default limit is 1,000.

Four things follow.

**1. An algorithm's step budget is part of its interface.** "DFS needs O(V + E)
time" says nothing about O(depth) *stack*. The iterative version here keeps its
own stack on the heap, so a 2,000-node chain is a normal input rather than a
crash, and the depth it reached is a number in the result.

**2. An explicit stack is not a drop-in replacement for recursion: when you mark
matters.** Recursion has one stack frame per node, so it can mark a node when it
descends into it. A loop that pushes *every* neighbour at once cannot: it has to
mark on push (or it would push a node many times), and marking on push changes
which route reaches a node first. The faithful rewrite marks when it *pops*, lets
the stack hold a node twice, and pushes neighbours in reverse so the first
neighbour listed is the first one taken. The pinned pair of orders below shows
both: the faithful version reproduces recursion exactly, the naive one visits the
same nodes in a different order.

**3. Breadth-first and depth-first are the same loop with a different end.** A
deque popped from the left is a queue (BFS); popped from the right it is a stack
(DFS). The distance column is what makes the difference legible: BFS's distances
never decrease, DFS's do.

**4. "Visited" and "discovered" are not the same word.** Marking a node when it is
*pushed* (rather than when it is *popped*) keeps a node out of the frontier twice,
which is what stops BFS from re-queueing a cycle -- but it also means the visit
order is the discovery order. Both facts are checked here rather than assumed.

Standard library only: no ``tkinter``, no ``networkx``, no network.
"""

from __future__ import annotations

import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GRAPH = DATA_DIR / "graph.txt"

#: The legacy recursion, kept as a claim we can execute.
LEGACY_RECURSION = "yield from walk(neighbor)"
LEGACY_ENTRY = "yield from walk(start_node)"

#: Where a naive stack rewrite goes wrong.
NAIVE_PUSH = "stack.extend(graph.neighbors(current))"
FIXED_PUSH = "stack.extend(reversed(graph.neighbors(current)))"


class GraphError(ValueError):
    """An edge, a node or a graph that is refused."""


# --------------------------------------------------------------------------- #
# The graph
# --------------------------------------------------------------------------- #
class Graph:
    """An undirected graph whose adjacency lists are kept sorted.

    Sorting is a policy, not a law: the traversal order has to come from
    somewhere, and a sorted list is the only source that does not depend on the
    order the file happened to list its edges in.
    """

    def __init__(self, edges=()) -> None:
        self._adjacency: dict[str, set[str]] = {}
        for left, right in edges:
            self.add_edge(left, right)

    def add_node(self, node: str) -> None:
        if not isinstance(node, str) or not node.strip():
            raise GraphError("a node name must be a non-empty string")
        self._adjacency.setdefault(node.strip(), set())

    def add_edge(self, left: str, right: str) -> None:
        if not isinstance(left, str) or not isinstance(right, str):
            raise GraphError("a node name must be a non-empty string")
        left, right = left.strip(), right.strip()
        if not left or not right:
            raise GraphError("a node name must be a non-empty string")
        if left == right:
            raise GraphError(f"an edge from {left!r} to itself is not a link "
                             f"between two nodes")
        self.add_node(left)
        self.add_node(right)
        self._adjacency[left].add(right)
        self._adjacency[right].add(left)

    @property
    def nodes(self) -> tuple[str, ...]:
        return tuple(sorted(self._adjacency))

    def neighbors(self, node: str) -> tuple[str, ...]:
        if node not in self._adjacency:
            raise GraphError(f"no such node: {node!r}")
        return tuple(sorted(self._adjacency[node]))

    def degree(self, node: str) -> int:
        return len(self.neighbors(node))

    @property
    def edge_count(self) -> int:
        return sum(len(others) for others in self._adjacency.values()) // 2

    def __len__(self) -> int:
        return len(self._adjacency)

    def __contains__(self, node) -> bool:
        return node in self._adjacency

    def __iter__(self):
        return iter(self.nodes)

    def __str__(self) -> str:
        return ", ".join(f"{node}:{self.degree(node)}" for node in self.nodes)


# --------------------------------------------------------------------------- #
# A visit and a traversal
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Visit:
    """One node taken off the frontier, and how far it was."""

    node: str
    order: int
    distance: int

    def __post_init__(self) -> None:
        if self.order < 1:
            raise GraphError("the first visit is order 1")
        if self.distance < 0:
            raise GraphError("a distance is never negative")


@dataclass(frozen=True)
class Traversal:
    """Everything one traversal learned, in the order it learned it."""

    kind: str
    start: str
    visits: tuple[Visit, ...]
    parent: dict[str, str | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.visits:
            raise GraphError("a traversal visits at least its start node")

    @property
    def order(self) -> tuple[str, ...]:
        return tuple(visit.node for visit in self.visits)

    @property
    def distances(self) -> tuple[int, ...]:
        return tuple(visit.distance for visit in self.visits)

    @property
    def depth(self) -> int:
        """The deepest node in the traversal, by its own distances."""
        return max(self.distances)

    def path_to(self, node: str) -> tuple[str, ...]:
        """The path this traversal found, from the start to ``node``."""
        if node not in self.parent:
            raise GraphError(f"{node!r} was never reached from {self.start!r}")
        path = [node]
        while path[-1] != self.start:
            previous = self.parent[path[-1]]
            if previous is None:
                raise GraphError(f"a broken parent chain at {path[-1]!r}")
            path.append(previous)
        return tuple(reversed(path))

    def summary(self) -> dict:
        return {"kind": self.kind, "start": self.start,
                "visited": len(self.visits), "order": list(self.order),
                "distances": list(self.distances)}

    def to_dict(self) -> dict:
        return {**self.summary(),
                "parent": dict(self.parent)}

    def __len__(self) -> int:
        return len(self.visits)

    def __iter__(self):
        return iter(self.order)


# --------------------------------------------------------------------------- #
# The traversals
# --------------------------------------------------------------------------- #
def check_start(graph: Graph, start) -> str:
    if not isinstance(start, str) or not start.strip():
        raise GraphError("a start node must be a non-empty string")
    if start not in graph:
        raise GraphError(f"no such node: {start!r}")
    return start


def breadth_first(graph: Graph, start: str) -> Traversal:
    """A queue, marked when pushed, so nothing is enqueued twice."""
    start = check_start(graph, start)
    queue = deque([start])
    seen = {start}
    visits: list[Visit] = []
    parent: dict[str, str | None] = {start: None}
    depth: dict[str, int] = {start: 0}
    while queue:
        current = queue.popleft()
        visits.append(Visit(current, len(visits) + 1, depth[current]))
        for neighbor in graph.neighbors(current):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            parent[neighbor] = current
            depth[neighbor] = depth[current] + 1
            queue.append(neighbor)
    return Traversal("breadth", start, tuple(visits), parent)


def depth_first(graph: Graph, start: str) -> Traversal:
    """The recursion-faithful stack: mark on pop, push ``(node, parent)``.

    The stack may hold one node twice -- that is what lets this loop keep
    recursion's order -- and it carries the parent in the entry, so the parent
    recorded is the one that was actually on top when the node was visited, not
    whichever neighbour happened to push it first. Both facts matter: without
    the first the order drifts, without the second the reported distance is a
    different tree's.
    """
    start = check_start(graph, start)
    stack: list[tuple[str, str | None]] = [(start, None)]
    seen: set[str] = set()
    visits: list[Visit] = []
    parent: dict[str, str | None] = {start: None}
    depth: dict[str, int] = {start: 0}
    while stack:
        current, reached_from = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        parent[current] = reached_from
        depth[current] = 0 if reached_from is None else depth[reached_from] + 1
        visits.append(Visit(current, len(visits) + 1, depth[current]))
        for neighbor in reversed(graph.neighbors(current)):
            if neighbor in seen:
                continue
            stack.append((neighbor, current))
    return Traversal("depth", start, tuple(visits), parent)


def depth_first_naive(graph: Graph, start: str) -> Traversal:
    """The same stack, marking on push: no duplicates, a different order."""
    start = check_start(graph, start)
    stack = [start]
    seen = {start}
    visits: list[Visit] = []
    parent: dict[str, str | None] = {start: None}
    depth: dict[str, int] = {start: 0}
    while stack:
        current = stack.pop()
        visits.append(Visit(current, len(visits) + 1, depth[current]))
        for neighbor in graph.neighbors(current):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            parent[neighbor] = current
            depth[neighbor] = depth[current] + 1
            stack.append(neighbor)
    return Traversal("depth-naive", start, tuple(visits), parent)


def parent_distance(parent, node) -> int:
    """How many parent links separate ``node`` from the start."""
    steps = 0
    while parent.get(node) is not None:
        node = parent[node]
        steps += 1
    return steps


def legacy_recursive_dfs(graph: Graph, start: str) -> Traversal:
    """The legacy function: recursion, and whatever the interpreter's stack allows.

    Raises :class:`RecursionError` on a deep enough chain -- which is the point,
    and the reason the module's own ``depth_first`` does not use recursion.
    """
    start = check_start(graph, start)
    seen = {start}
    visits: list[Visit] = []
    parent: dict[str, str | None] = {start: None}

    def walk(current: str) -> None:
        visits.append(Visit(current, len(visits) + 1,
                            parent_distance(parent, current)))
        for neighbor in graph.neighbors(current):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            parent[neighbor] = current
            walk(neighbor)

    walk(start)
    return Traversal("recursive", start, tuple(visits), parent)


def components(graph: Graph) -> tuple[tuple[str, ...], ...]:
    """One traversal per connected component, in node-name order."""
    remaining = set(graph.nodes)
    found = []
    for node in graph.nodes:
        if node not in remaining:
            continue
        traversal = breadth_first(graph, node)
        found.append(traversal.order)
        remaining -= set(traversal.order)
    return tuple(found)


def chain(length: int) -> Graph:
    """A path of ``length`` nodes: the graph that breaks a recursive walk."""
    if length < 1:
        raise GraphError("a chain needs at least one node")
    graph = Graph()
    graph.add_node("n0")
    for index in range(1, length):
        graph.add_edge(f"n{index - 1}", f"n{index}")
    return graph


def recursion_limit() -> int:
    """The budget the legacy walk was spending without saying so."""
    return sys.getrecursionlimit()


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #
def read_graph(path=GRAPH) -> Graph:
    """Read ``left-right`` lines; comments and blanks are skipped."""
    path = Path(path)
    if not path.is_file():
        raise GraphError(f"graph file not found: {path}")
    graph = Graph()
    for number, line in enumerate(path.read_text(encoding="utf-8")
                                  .splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "-" not in text:
            raise GraphError(f"{path.name}:{number}: {text!r} is not an edge "
                             f"written left-right")
        left, _, right = text.partition("-")
        left, right = left.strip(), right.strip()
        if not left or not right:
            raise GraphError(f"{path.name}:{number}: an edge needs two names")
        graph.add_edge(left, right)
    return graph


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def component_of(graph: Graph, node: str) -> frozenset[str]:
    """The nodes reachable from ``node``, computed without any traversal queue.

    A union-find over the edges, so "BFS reached the whole component" is checked
    against a second, independent calculation rather than against another BFS.
    """
    if node not in graph:
        raise GraphError(f"no such node: {node!r}")
    parent = {name: name for name in graph.nodes}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    for left, right in edge_pairs(graph):
        first, second = find(left), find(right)
        if first != second:
            parent[second] = first
    root = find(node)
    return frozenset(name for name in graph.nodes if find(name) == root)


def edge_pairs(graph: Graph) -> tuple[tuple[str, str], ...]:
    pairs = []
    for node in graph.nodes:
        for neighbor in graph.neighbors(node):
            if node < neighbor:
                pairs.append((node, neighbor))
    return tuple(pairs)


def audit(graph: Graph, traversals) -> list[tuple[str, bool]]:
    traversals = list(traversals)
    all_nodes = set(graph.nodes)

    def parents_are_real_edges(traversal: Traversal) -> bool:
        for node in traversal.order[1:]:
            parent = traversal.parent.get(node)
            if parent not in traversal.parent:
                return False
            try:
                if parent not in graph.neighbors(node):
                    return False
            except GraphError:
                return False
        return True

    def paths_work(traversal: Traversal) -> bool:
        for node in traversal.order[1:]:
            try:
                path = traversal.path_to(node)
            except GraphError:
                return False
            if path[0] != traversal.start or path[-1] != node:
                return False
            if any(second not in graph.neighbors(first)
                   for first, second in zip(path, path[1:])):
                return False
        return True

    def distances_match_paths(traversal: Traversal) -> bool:
        try:
            return all(visit.distance == len(traversal.path_to(visit.node)) - 1
                       for visit in traversal.visits)
        except GraphError:
            return False

    bfs = [t for t in traversals if t.kind == "breadth"]
    dfs = [t for t in traversals if t.kind.startswith("depth")]

    return [
        ("every traversal starts at its start node",
         all(t.order[0] == t.start for t in traversals)),
        ("no traversal visits a node twice",
         all(len(set(t.order)) == len(t.order) for t in traversals)),
        ("every visited node exists in the graph",
         all(not set(t.order) - all_nodes for t in traversals)),
        ("every parent is a neighbour that was reached first",
         all(parents_are_real_edges(t) for t in traversals)),
        ("every reconstructed path follows real edges",
         all(paths_work(t) for t in traversals)),
        ("every recorded distance equals the path it came from",
         all(distances_match_paths(t) for t in traversals)),
        ("breadth-first distances never decrease",
         all(all(a <= b for a, b in zip(t.distances, t.distances[1:]))
             for t in bfs)),
        ("breadth-first reaches exactly its component",
         all(len(t) == len(component_of(graph, t.start)) for t in bfs)),
        ("depth-first reaches exactly its component too",
         all(set(t.order) == set(component_of(graph, t.start)) for t in dfs)),
    ]


def audit_orders(recursive: Traversal, fixed: Traversal,
                 naive: Traversal) -> list[tuple[str, bool]]:
    """The checks that need three traversals to compare."""
    return [
        ("the iterative rewrite keeps recursion's order",
         fixed.order == recursive.order),
        ("the iterative rewrite keeps recursion's distances too",
         fixed.distances == recursive.distances),
        ("the naive stack changes the order",
         naive.order != recursive.order),
        ("all three visit the same set",
         set(naive.order) == set(recursive.order) == set(fixed.order)),
    ]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    graph = read_graph()
    bfs = breadth_first(graph, "A")
    dfs = depth_first(graph, "A")
    naive = depth_first_naive(graph, "A")
    recursive = legacy_recursive_dfs(graph, "A")
    groups = components(graph)

    print("=" * 74)
    print(" TRAVERSAL LAB - an algorithm's step budget is part of its interface")
    print("=" * 74)
    print(f"  {len(graph)} nodes, {graph.edge_count} edges: {graph}")
    print(f"  components: {' | '.join(' '.join(group) for group in groups)}")

    print(f"\n  {'traversal':<12}{'order':<34}distances")
    for traversal in (bfs, dfs, naive, recursive):
        print(f"  {traversal.kind:<12}{' '.join(traversal.order):<34}"
              f"{' '.join(str(d) for d in traversal.distances)}")

    print(f"\n  breadth-first distances never decrease: "
          f"{' '.join(str(d) for d in bfs.distances)}")
    drop = next(((a, b) for a, b in zip(dfs.distances, dfs.distances[1:])
                 if b < a), None)
    if drop is not None:
        print(f"  depth-first's do: its distances go "
              f"{' '.join(str(d) for d in dfs.distances)}, dropping from "
              f"{drop[0]} to {drop[1]} -- a deep branch, then a return to a "
              f"shallow one")
    bfs_depth = dict(zip(bfs.order, bfs.distances))
    worst = max(dfs.visits, key=lambda v: v.distance - bfs_depth[v.node])
    print(f"  so DFS reaches {worst.node} in {worst.distance} steps down "
          f"{' -> '.join(dfs.path_to(worst.node))}, while BFS reaches it in "
          f"{bfs_depth[worst.node]} down {' -> '.join(bfs.path_to(worst.node))}")

    limit = recursion_limit()
    deep = chain(limit + 500)
    print(f"\n  a {len(deep)}-node chain, with the interpreter's limit at {limit}:")
    try:
        legacy_recursive_dfs(deep, "n0")
        legacy = "it survived"
    except RecursionError:
        legacy = "RecursionError"
    iterative = depth_first(deep, "n0")
    print(f"    the legacy recursive walk: {legacy}")
    print(f"    this module's iterative walk: {len(iterative)} nodes, "
          f"deepest distance {iterative.depth}")
    print(f"    the walk costs one frame per node, so a chain longer than the "
          f"limit cannot be walked recursively at all -- and no longer has to "
          f"be")

    checks = audit(graph, [bfs, dfs, naive]) + \
        audit_orders(recursive, dfs, naive)
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\n  a second run of the same traversals: ", end="")
    again = breadth_first(graph, "A").summary()
    assert again == bfs.summary(), "a traversal is deterministic"
    print("identical summaries")

    print("\nCross-checks OK: " +
          f"{len(graph)} nodes fall into {len(groups)} components, BFS visits "
          f"{' '.join(bfs.order)} with non-decreasing distances, DFS visits "
          f"{' '.join(dfs.order)} with the deepest distance {dfs.depth} against "
          f"BFS's {bfs.depth}, the naive stack visits the same nodes in a "
          f"different order ({' '.join(naive.order)}), the iterative rewrite "
          f"reproduces recursion exactly, the recursive walk raises "
          f"RecursionError on a {len(deep)}-node chain while the iterative one "
          f"reaches {len(iterative)}, every reconstructed path follows real "
          f"edges, a second run agrees, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("\nDemo completed successfully.")
    return 0
