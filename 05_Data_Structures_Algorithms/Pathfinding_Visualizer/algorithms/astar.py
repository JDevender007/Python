"""A* search implementation for the visualizer grid."""

from __future__ import annotations

import heapq
import itertools
from math import inf
from time import perf_counter

from algorithms import SearchResult, finalize_result, reconstruct_path
from src.grid import GridModel
from src.node import Node
from src.utils import manhattan_distance


def astar_search(grid: GridModel, start: Node, end: Node) -> SearchResult:
    """Find a shortest path using Manhattan-distance A* search."""
    started_at = perf_counter()
    counter = itertools.count()
    frontier: list[tuple[float, int, Node]] = [
        (float(manhattan_distance(start, end)), next(counter), start)
    ]
    came_from: dict[Node, Node] = {}
    g_score: dict[Node, float] = {start: 0.0}
    queued_best: dict[Node, float] = {
        start: float(manhattan_distance(start, end))
    }
    visited: set[Node] = set()
    visited_order: list[Node] = []

    while frontier:
        current_f, _, current = heapq.heappop(frontier)
        if current in visited:
            continue
        if current_f > queued_best.get(current, inf):
            continue

        visited.add(current)
        visited_order.append(current)
        if current == end:
            path = reconstruct_path(came_from, start, end)
            return finalize_result(started_at, visited_order, path)

        for neighbor in grid.neighbors(current):
            if neighbor in visited:
                continue
            tentative_g = g_score[current] + 1.0
            if tentative_g >= g_score.get(neighbor, inf):
                continue

            came_from[neighbor] = current
            g_score[neighbor] = tentative_g
            f_score = tentative_g + manhattan_distance(neighbor, end)
            queued_best[neighbor] = f_score
            heapq.heappush(frontier, (f_score, next(counter), neighbor))

    return finalize_result(started_at, visited_order, ())
