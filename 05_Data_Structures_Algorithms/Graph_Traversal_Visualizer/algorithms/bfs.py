"""Breadth-first search implementation."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator

from algorithms.graph import Graph
from algorithms.traversal_utils import (
    TraversalEvent,
    TraversalStep,
    validate_start_node,
)


def breadth_first_steps(graph: Graph, start_node: int) -> Iterator[TraversalStep]:
    """Yield deterministic, animation-ready breadth-first search steps."""
    validate_start_node(graph, start_node)

    discovered = {start_node}
    queue: deque[int] = deque([start_node])
    order: list[int] = []

    yield TraversalStep(
        TraversalEvent.START,
        current=start_node,
        message=f"Starting BFS at node {start_node}",
    )

    order.append(start_node)
    yield TraversalStep(
        TraversalEvent.VISIT,
        current=start_node,
        target=start_node,
        visited_order=tuple(order),
        message=f"Visited node {start_node}",
    )

    while queue:
        current = queue.popleft()
        for neighbor in graph.neighbors(current):
            if neighbor in discovered:
                continue
            discovered.add(neighbor)
            queue.append(neighbor)
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

    yield TraversalStep(
        TraversalEvent.COMPLETE,
        current=order[-1],
        visited_order=tuple(order),
        message="Breadth-first traversal complete",
    )
