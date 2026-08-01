"""Complexity information displayed by the control panel."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComplexityInfo:
    """Human-readable algorithm complexity summary."""

    best_case: str
    average_case: str
    worst_case: str
    space: str
    note: str


COMPLEXITIES: dict[str, ComplexityInfo] = {
    "A* Search": ComplexityInfo(
        best_case="O(1)",
        average_case="Heuristic-dependent",
        worst_case="O((V + E) log V)",
        space="O(V)",
        note="Performance depends strongly on heuristic quality.",
    ),
    "Dijkstra": ComplexityInfo(
        best_case="O(1)",
        average_case="O((V + E) log V)",
        worst_case="O((V + E) log V)",
        space="O(V)",
        note="Uses a binary heap priority queue.",
    ),
    "Breadth First Search": ComplexityInfo(
        best_case="O(1)",
        average_case="O(V + E)",
        worst_case="O(V + E)",
        space="O(V)",
        note="Guarantees a shortest path on this unweighted grid.",
    ),
    "Depth First Search": ComplexityInfo(
        best_case="O(1)",
        average_case="O(V + E)",
        worst_case="O(V + E)",
        space="O(V)",
        note="Finds a path, but not necessarily the shortest path.",
    ),
    "Greedy Best First Search": ComplexityInfo(
        best_case="O(1)",
        average_case="Heuristic-dependent",
        worst_case="O((V + E) log V)",
        space="O(V)",
        note="Fast in many layouts, but does not guarantee optimality.",
    ),
}


def get_complexity(algorithm_name: str) -> ComplexityInfo:
    """Return complexity information for a supported algorithm."""
    try:
        return COMPLEXITIES[algorithm_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported algorithm: {algorithm_name}") from exc
