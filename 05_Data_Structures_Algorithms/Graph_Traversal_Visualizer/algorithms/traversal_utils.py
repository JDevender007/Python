"""Shared traversal event types and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from algorithms.graph import Graph


class TraversalEvent(Enum):
    """Events emitted by graph traversal generators."""

    START = auto()
    EDGE = auto()
    VISIT = auto()
    COMPLETE = auto()


@dataclass(frozen=True, slots=True)
class TraversalStep:
    """One animation-ready traversal event."""

    event: TraversalEvent
    current: int | None = None
    source: int | None = None
    target: int | None = None
    visited_order: tuple[int, ...] = ()
    message: str = ""


def validate_start_node(graph: Graph, start_node: int) -> None:
    """Validate that a traversal can begin from ``start_node``."""
    if graph.node_count == 0:
        raise ValueError("Cannot traverse an empty graph.")
    if start_node not in graph:
        raise ValueError(f"Start node {start_node} does not exist.")
