"""Depth-first search implementation."""

from __future__ import annotations

from time import perf_counter

from algorithms import SearchResult, finalize_result, reconstruct_path
from src.grid import GridModel
from src.node import Node


def depth_first_search(
    grid: GridModel, start: Node, end: Node
) -> SearchResult:
    """Search for a path using iterative depth-first traversal."""
    started_at = perf_counter()
    stack = [start]
    discovered = {start}
    came_from: dict[Node, Node] = {}
    visited_order: list[Node] = []

    while stack:
        current = stack.pop()
        visited_order.append(current)
        if current == end:
            path = reconstruct_path(came_from, start, end)
            return finalize_result(started_at, visited_order, path)

        # Reverse the deterministic neighbor order so DFS visually advances
        # right/down before backtracking when possible.
        for neighbor in reversed(grid.neighbors(current)):
            if neighbor in discovered:
                continue
            discovered.add(neighbor)
            came_from[neighbor] = current
            stack.append(neighbor)

    return finalize_result(started_at, visited_order, ())
