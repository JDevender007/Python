"""Grid data model and topology operations."""

from __future__ import annotations

import random
from collections.abc import Iterator

from src.node import Node


class GridModel:
    """Owns grid nodes, endpoints, walls, and neighbor relationships."""

    def __init__(self, rows: int, columns: int) -> None:
        self._validate_dimensions(rows, columns)
        self.rows = rows
        self.columns = columns
        self.nodes: list[list[Node]] = []
        self.start_node: Node | None = None
        self.end_node: Node | None = None
        self._create_nodes()

    @staticmethod
    def _validate_dimensions(rows: int, columns: int) -> None:
        if rows < 2 or columns < 2:
            raise ValueError("Grid dimensions must both be at least 2.")

    def _create_nodes(self) -> None:
        self.nodes = [
            [Node(row=row, column=column) for column in range(self.columns)]
            for row in range(self.rows)
        ]
        self.start_node = None
        self.end_node = None

    def __iter__(self) -> Iterator[Node]:
        for row in self.nodes:
            yield from row

    def resize(self, rows: int, columns: int) -> None:
        """Replace the grid with a clean grid using new dimensions."""
        self._validate_dimensions(rows, columns)
        self.rows = rows
        self.columns = columns
        self._create_nodes()

    def node_at(self, row: int, column: int) -> Node | None:
        """Return a node by coordinates, or ``None`` when out of bounds."""
        if 0 <= row < self.rows and 0 <= column < self.columns:
            return self.nodes[row][column]
        return None

    def neighbors(self, node: Node) -> list[Node]:
        """Return traversable orthogonal neighbors in deterministic order."""
        candidates = (
            (node.row, node.column + 1),
            (node.row + 1, node.column),
            (node.row, node.column - 1),
            (node.row - 1, node.column),
        )
        result: list[Node] = []
        for row, column in candidates:
            neighbor = self.node_at(row, column)
            if neighbor is not None and not neighbor.is_wall:
                result.append(neighbor)
        return result

    def set_start(self, node: Node) -> None:
        """Set ``node`` as the unique start node."""
        if node.is_end:
            return
        if self.start_node is not None:
            self.start_node.is_start = False
        node.is_wall = False
        node.reset_search_state()
        node.is_start = True
        self.start_node = node

    def set_end(self, node: Node) -> None:
        """Set ``node`` as the unique destination node."""
        if node.is_start:
            return
        if self.end_node is not None:
            self.end_node.is_end = False
        node.is_wall = False
        node.reset_search_state()
        node.is_end = True
        self.end_node = node

    def set_wall(self, node: Node, enabled: bool) -> None:
        """Add or remove a wall without overwriting endpoints."""
        if node.is_start or node.is_end:
            return
        node.reset_search_state()
        node.is_wall = enabled

    def erase_node(self, node: Node) -> None:
        """Erase a wall or endpoint from a node."""
        if node.is_start:
            self.start_node = None
        if node.is_end:
            self.end_node = None
        node.clear()

    def clear_search(self) -> None:
        """Clear visited/path states while preserving endpoints and walls."""
        for node in self:
            node.reset_search_state()

    def clear_all(self) -> None:
        """Restore every node and remove both endpoints."""
        for node in self:
            node.clear()
        self.start_node = None
        self.end_node = None

    def ensure_default_endpoints(self) -> None:
        """Create sensible endpoints when one or both are missing."""
        center_row = self.rows // 2
        if self.start_node is None:
            self.set_start(self.nodes[center_row][max(1, self.columns // 6)])
        if self.end_node is None:
            self.set_end(
                self.nodes[center_row][min(self.columns - 2, self.columns * 5 // 6)]
            )

    def generate_random_maze(
        self,
        density: float = 0.28,
        seed: int | None = None,
    ) -> None:
        """Generate a random, endpoint-safe maze with a guaranteed corridor."""
        if not 0.0 <= density <= 0.75:
            raise ValueError("Maze density must be between 0.0 and 0.75.")

        generator = random.Random(seed)
        self.clear_all()
        self.ensure_default_endpoints()

        for node in self:
            if node.is_start or node.is_end:
                continue
            node.is_wall = generator.random() < density

        if self.start_node is None or self.end_node is None:
            return

        # Carve a simple guaranteed route. Randomizing the turn direction keeps
        # generated layouts varied while ensuring every maze remains usable.
        start = self.start_node
        end = self.end_node
        if generator.choice((True, False)):
            self._carve_horizontal(start.row, start.column, end.column)
            self._carve_vertical(end.column, start.row, end.row)
        else:
            self._carve_vertical(start.column, start.row, end.row)
            self._carve_horizontal(end.row, start.column, end.column)

    def _carve_horizontal(self, row: int, first: int, last: int) -> None:
        for column in range(min(first, last), max(first, last) + 1):
            self.nodes[row][column].is_wall = False

    def _carve_vertical(self, column: int, first: int, last: int) -> None:
        for row in range(min(first, last), max(first, last) + 1):
            self.nodes[row][column].is_wall = False
