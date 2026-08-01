"""Pathfinding algorithm interfaces and shared utilities."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Mapping, TypeAlias

from src.node import Node


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Immutable result produced by a pathfinding algorithm."""

    visited_order: tuple[Node, ...]
    path: tuple[Node, ...]
    execution_time_ms: float
    found: bool


AlgorithmFunction: TypeAlias = Callable[["GridModel", Node, Node], SearchResult]


def reconstruct_path(
    came_from: Mapping[Node, Node], start: Node, end: Node
) -> tuple[Node, ...]:
    """Reconstruct a path from a predecessor mapping.

    Args:
        came_from: Mapping from a node to the node used to reach it.
        start: Starting node.
        end: Destination node.

    Returns:
        The path from ``start`` to ``end`` (inclusive), or an empty tuple when
        the destination was not reached.
    """
    if end != start and end not in came_from:
        return ()

    current = end
    path = [current]
    while current != start:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return tuple(path)


def finalize_result(
    started_at: float,
    visited_order: list[Node],
    path: tuple[Node, ...],
) -> SearchResult:
    """Create a timed :class:`SearchResult`."""
    elapsed_ms = (perf_counter() - started_at) * 1_000.0
    return SearchResult(
        visited_order=tuple(visited_order),
        path=path,
        execution_time_ms=elapsed_ms,
        found=bool(path),
    )


# Imported at the end to keep shared definitions available during module import.
from algorithms.astar import astar_search  # noqa: E402
from algorithms.bfs import breadth_first_search  # noqa: E402
from algorithms.dfs import depth_first_search  # noqa: E402
from algorithms.dijkstra import dijkstra_search  # noqa: E402
from algorithms.greedy_best_first import greedy_best_first_search  # noqa: E402

ALGORITHMS: dict[str, AlgorithmFunction] = {
    "A* Search": astar_search,
    "Dijkstra": dijkstra_search,
    "Breadth First Search": breadth_first_search,
    "Depth First Search": depth_first_search,
    "Greedy Best First Search": greedy_best_first_search,
}


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.grid import GridModel


__all__ = [
    "ALGORITHMS",
    "AlgorithmFunction",
    "SearchResult",
    "astar_search",
    "breadth_first_search",
    "depth_first_search",
    "dijkstra_search",
    "greedy_best_first_search",
]
