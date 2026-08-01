"""Dijkstra shortest-path search implementation."""

from __future__ import annotations

import heapq
import itertools
from math import inf
from time import perf_counter

from algorithms import SearchResult, finalize_result, reconstruct_path
from src.grid import GridModel
from src.node import Node


def dijkstra_search(grid: GridModel, start: Node, end: Node) -> SearchResult:
    """Find a shortest path with Dijkstra's algorithm on a unit-cost grid."""
    started_at = perf_counter()
    counter = itertools.count()
    frontier: list[tuple[float, int, Node]] = [(0.0, next(counter), start)]
    distances: dict[Node, float] = {start: 0.0}
    came_from: dict[Node, Node] = {}
    visited: set[Node] = set()
    visited_order: list[Node] = []

    while frontier:
        distance, _, current = heapq.heappop(frontier)
        if current in visited:
            continue
        if distance > distances.get(current, inf):
            continue

        visited.add(current)
        visited_order.append(current)
        if current == end:
            path = reconstruct_path(came_from, start, end)
            return finalize_result(started_at, visited_order, path)

        for neighbor in grid.neighbors(current):
            tentative = distance + 1.0
            if tentative >= distances.get(neighbor, inf):
                continue
            distances[neighbor] = tentative
            came_from[neighbor] = current
            heapq.heappush(frontier, (tentative, next(counter), neighbor))

    return finalize_result(started_at, visited_order, ())
