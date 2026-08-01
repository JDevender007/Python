"""Small reusable utility functions."""

from __future__ import annotations

from src.node import Node


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp ``value`` to the inclusive range provided."""
    return max(minimum, min(maximum, value))


def manhattan_distance(first: Node, second: Node) -> int:
    """Return Manhattan distance between two grid nodes."""
    return abs(first.row - second.row) + abs(first.column - second.column)


def format_duration(milliseconds: float) -> str:
    """Format milliseconds for the statistics panel."""
    if milliseconds < 1.0:
        return f"{milliseconds * 1_000.0:.1f} µs"
    if milliseconds < 1_000.0:
        return f"{milliseconds:.2f} ms"
    return f"{milliseconds / 1_000.0:.2f} s"
