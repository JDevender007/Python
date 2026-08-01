"""Depth-first search implementation."""

from __future__ import annotations

from collections.abc import Iterator

from algorithms.graph import Graph
from algorithms.traversal_utils import (
    TraversalEvent,
    TraversalStep,
    validate_start_node,
)


def depth_first_steps(graph: Graph, start_node: int) -> Iterator[TraversalStep]:
    """Yield deterministic, animation-ready depth-first search steps."""
    validate_start_node(graph, start_node)

    visited: set[int] = {start_node}
    order: list[int] = [start_node]

    yield TraversalStep(
        TraversalEvent.START,
        current=start_node,
        message=f"Starting DFS at node {start_node}",
    )
    yield TraversalStep(
        TraversalEvent.VISIT,
        current=start_node,
        target=start_node,
        visited_order=tuple(order),
        message=f"Visited node {start_node}",
    )

    def walk(current: int) -> Iterator[TraversalStep]:
        for neighbor in graph.neighbors(current):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            yield TraversalStep(
                TraversalEvent.EDGE,
                current=current,
                source=current,
                target=neighbor,
                visited_order=tuple(order),
                message=f"Exploring edge {current} → {neighbor}",
            )
            order.append(neighbor)
            yield TraversalStep(
                TraversalEvent.VISIT,
                current=neighbor,
                source=current,
                target=neighbor,
                visited_order=tuple(order),
                message=f"Visited node {neighbor}",
            )
            yield from walk(neighbor)

    yield from walk(start_node)
    yield TraversalStep(
        TraversalEvent.COMPLETE,
        current=order[-1],
        visited_order=tuple(order),
        message="Depth-first traversal complete",
    )
