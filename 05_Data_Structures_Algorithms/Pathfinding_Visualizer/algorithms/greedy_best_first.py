"""Greedy best-first search implementation."""

from __future__ import annotations

import heapq
import itertools
from time import perf_counter

from algorithms import SearchResult, finalize_result, reconstruct_path
from src.grid import GridModel
from src.node import Node
from src.utils import manhattan_distance


def greedy_best_first_search(
    grid: GridModel, start: Node, end: Node
) -> SearchResult:
    """Find a path by prioritizing nodes closest to the destination."""
    started_at = perf_counter()
    counter = itertools.count()
    frontier: list[tuple[int, int, Node]] = [
        (manhattan_distance(start, end), next(counter), start)
    ]
    discovered = {start}
    came_from: dict[Node, Node] = {}
    visited_order: list[Node] = []

    while frontier:
        _, _, current = heapq.heappop(frontier)
        visited_order.append(current)
        if current == end:
            path = reconstruct_path(came_from, start, end)
            return finalize_result(started_at, visited_order, path)

        for neighbor in grid.neighbors(current):
            if neighbor in discovered:
                continue
            discovered.add(neighbor)
            came_from[neighbor] = current
            priority = manhattan_distance(neighbor, end)
            heapq.heappush(frontier, (priority, next(counter), neighbor))

    return finalize_result(started_at, visited_order, ())
