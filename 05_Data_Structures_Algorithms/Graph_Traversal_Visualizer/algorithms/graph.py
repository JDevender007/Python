"""Undirected weighted graph model used by the visualizer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(slots=True)
class Node:
    """A graph vertex positioned in normalized canvas coordinates."""

    node_id: int
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Edge:
    """An undirected weighted edge."""

    source: int
    target: int
    weight: float

    @property
    def key(self) -> tuple[int, int]:
        """Return a stable key independent of edge direction."""
        return tuple(sorted((self.source, self.target)))


class Graph:
    """A mutable undirected graph with deterministic neighbor ordering."""

    def __init__(self) -> None:
        self._nodes: dict[int, Node] = {}
        self._adjacency: dict[int, dict[int, float]] = {}
        self._next_node_id = 0

    @property
    def nodes(self) -> tuple[Node, ...]:
        """Return nodes ordered by identifier."""
        return tuple(self._nodes[node_id] for node_id in sorted(self._nodes))

    @property
    def edges(self) -> tuple[Edge, ...]:
        """Return each undirected edge exactly once."""
        result: list[Edge] = []
        for source in sorted(self._adjacency):
            for target, weight in sorted(self._adjacency[source].items()):
                if source < target:
                    result.append(Edge(source, target, weight))
        return tuple(result)

    @property
    def node_count(self) -> int:
        """Return the number of vertices."""
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        """Return the number of undirected edges."""
        return sum(len(neighbors) for neighbors in self._adjacency.values()) // 2

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._nodes

    def add_node(
        self,
        x: float,
        y: float,
        node_id: int | None = None,
    ) -> int:
        """Add a node and return its identifier.

        Coordinates are clamped to the normalized range ``[0.0, 1.0]``.
        """
        assigned_id = self._next_node_id if node_id is None else node_id
        if assigned_id in self._nodes:
            raise ValueError(f"Node {assigned_id} already exists.")
        if assigned_id < 0:
            raise ValueError("Node identifiers must be non-negative.")

        self._nodes[assigned_id] = Node(
            assigned_id,
            self._clamp_coordinate(x),
            self._clamp_coordinate(y),
        )
        self._adjacency[assigned_id] = {}
        self._next_node_id = max(self._next_node_id, assigned_id + 1)
        return assigned_id

    def remove_node(self, node_id: int) -> None:
        """Remove a node and all incident edges."""
        self._require_node(node_id)
        for neighbor in tuple(self._adjacency[node_id]):
            self._adjacency[neighbor].pop(node_id, None)
        del self._adjacency[node_id]
        del self._nodes[node_id]

    def move_node(self, node_id: int, x: float, y: float) -> None:
        """Move a node to normalized coordinates."""
        self._require_node(node_id)
        node = self._nodes[node_id]
        node.x = self._clamp_coordinate(x)
        node.y = self._clamp_coordinate(y)

    def add_edge(self, source: int, target: int, weight: float = 1.0) -> None:
        """Add or update an undirected weighted edge."""
        self._require_node(source)
        self._require_node(target)
        if source == target:
            raise ValueError("Self-loops are not supported.")
        if weight <= 0:
            raise ValueError("Edge weight must be positive.")
        numeric_weight = float(weight)
        self._adjacency[source][target] = numeric_weight
        self._adjacency[target][source] = numeric_weight

    def remove_edge(self, source: int, target: int) -> None:
        """Remove an undirected edge."""
        self._require_node(source)
        self._require_node(target)
        if target not in self._adjacency[source]:
            raise ValueError(f"Edge {source}-{target} does not exist.")
        del self._adjacency[source][target]
        del self._adjacency[target][source]

    def has_edge(self, source: int, target: int) -> bool:
        """Return whether an edge exists."""
        return source in self._adjacency and target in self._adjacency[source]

    def neighbors(self, node_id: int) -> tuple[int, ...]:
        """Return neighboring node identifiers in ascending order."""
        self._require_node(node_id)
        return tuple(sorted(self._adjacency[node_id]))

    def edge_weight(self, source: int, target: int) -> float:
        """Return an edge's weight."""
        self._require_node(source)
        self._require_node(target)
        try:
            return self._adjacency[source][target]
        except KeyError as exc:
            raise ValueError(f"Edge {source}-{target} does not exist.") from exc

    def get_node(self, node_id: int) -> Node:
        """Return a node by identifier."""
        self._require_node(node_id)
        return self._nodes[node_id]

    def clear(self) -> None:
        """Remove all nodes and edges."""
        self._nodes.clear()
        self._adjacency.clear()
        self._next_node_id = 0

    def snapshot(self) -> dict[str, Any]:
        """Return a serializable deep snapshot of the graph."""
        return {
            "nodes": [
                {"node_id": node.node_id, "x": node.x, "y": node.y}
                for node in self.nodes
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "weight": edge.weight,
                }
                for edge in self.edges
            ],
        }

    def restore(self, snapshot: dict[str, Any]) -> None:
        """Restore a graph from :meth:`snapshot` output."""
        self.clear()
        try:
            nodes: Iterable[dict[str, Any]] = snapshot["nodes"]
            edges: Iterable[dict[str, Any]] = snapshot["edges"]
            for node in nodes:
                self.add_node(
                    float(node["x"]),
                    float(node["y"]),
                    int(node["node_id"]),
                )
            for edge in edges:
                self.add_edge(
                    int(edge["source"]),
                    int(edge["target"]),
                    float(edge["weight"]),
                )
        except (KeyError, TypeError, ValueError) as exc:
            self.clear()
            raise ValueError("Invalid graph snapshot.") from exc

    def validate(self) -> None:
        """Raise ``ValueError`` if internal graph invariants are broken."""
        if set(self._nodes) != set(self._adjacency):
            raise ValueError("Node and adjacency indexes are inconsistent.")
        for source, neighbors in self._adjacency.items():
            for target, weight in neighbors.items():
                if target not in self._nodes:
                    raise ValueError(f"Edge references missing node {target}.")
                if source not in self._adjacency[target]:
                    raise ValueError("Undirected edge is missing its reverse entry.")
                if self._adjacency[target][source] != weight:
                    raise ValueError("Undirected edge weights are inconsistent.")
                if source == target:
                    raise ValueError("Self-loops are not supported.")
                if weight <= 0:
                    raise ValueError("Edge weights must be positive.")

    @staticmethod
    def _clamp_coordinate(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _require_node(self, node_id: int) -> None:
        if node_id not in self._nodes:
            raise ValueError(f"Node {node_id} does not exist.")
