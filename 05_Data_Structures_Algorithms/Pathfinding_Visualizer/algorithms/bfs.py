"""Breadth-first search implementation."""

from __future__ import annotations

from collections import deque
from time import perf_counter

from algorithms import SearchResult, finalize_result, reconstruct_path
from src.grid import GridModel
from src.node import Node


def breadth_first_search(
    grid: GridModel, start: Node, end: Node
) -> SearchResult:
    """Find a shortest path in an unweighted grid using BFS."""
    started_at = perf_counter()
    frontier = deque([start])
    discovered = {start}
    came_from: dict[Node, Node] = {}
    visited_order: list[Node] = []

    while frontier:
        current = frontier.popleft()
        visited_order.append(current)
        if current == end:
            path = reconstruct_path(came_from, start, end)
            return finalize_result(started_at, visited_order, path)

        for neighbor in grid.neighbors(current):
            if neighbor in discovered:
                continue
            discovered.add(neighbor)
            came_from[neighbor] = current
            frontier.append(neighbor)

    return finalize_result(started_at, visited_order, ())
