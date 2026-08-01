"""Grid node model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NodeState(str, Enum):
    """Visual state of a node in the grid."""

    EMPTY = "empty"
    WALL = "wall"
    START = "start"
    END = "end"
    VISITED = "visited"
    PATH = "path"


@dataclass(eq=False, slots=True)
class Node:
    """A single cell in the pathfinding grid."""

    row: int
    column: int
    is_wall: bool = False
    is_start: bool = False
    is_end: bool = False
    is_visited: bool = False
    is_path: bool = False

    def __hash__(self) -> int:
        """Hash nodes by their immutable grid coordinates."""
        return hash((self.row, self.column))

    def __eq__(self, other: object) -> bool:
        """Compare nodes by grid coordinates."""
        if not isinstance(other, Node):
            return NotImplemented
        return self.row == other.row and self.column == other.column

    @property
    def state(self) -> NodeState:
        """Return the highest-priority visual state for the node."""
        if self.is_start:
            return NodeState.START
        if self.is_end:
            return NodeState.END
        if self.is_path:
            return NodeState.PATH
        if self.is_visited:
            return NodeState.VISITED
        if self.is_wall:
            return NodeState.WALL
        return NodeState.EMPTY

    def reset_search_state(self) -> None:
        """Remove visited and path markers while preserving topology."""
        self.is_visited = False
        self.is_path = False

    def clear(self) -> None:
        """Restore the node to an empty state."""
        self.is_wall = False
        self.is_start = False
        self.is_end = False
        self.reset_search_state()
