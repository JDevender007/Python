"""General-purpose application utilities."""

from __future__ import annotations

import math
import tkinter as tk
from collections.abc import Iterable
from typing import TypeVar

T = TypeVar("T", int, float)


def clamp(value: T, minimum: T, maximum: T) -> T:
    """Clamp ``value`` to an inclusive range."""
    return max(minimum, min(maximum, value))


def lerp(start: float, end: float, amount: float) -> float:
    """Linearly interpolate between two values."""
    return start + (end - start) * clamp(amount, 0.0, 1.0)


def ease_in_out_cubic(amount: float) -> float:
    """Return a smooth cubic easing value in the range ``[0, 1]``."""
    value = clamp(amount, 0.0, 1.0)
    if value < 0.5:
        return 4.0 * value * value * value
    return 1.0 - ((-2.0 * value + 2.0) ** 3) / 2.0


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Return Euclidean distance between two points."""
    return math.hypot(x2 - x1, y2 - y1)


def point_segment_distance(
    px: float,
    py: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> float:
    """Return the shortest distance from a point to a line segment."""
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return distance(px, py, x1, y1)
    projection = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    projection = clamp(projection, 0.0, 1.0)
    nearest_x = x1 + projection * dx
    nearest_y = y1 + projection * dy
    return distance(px, py, nearest_x, nearest_y)


def center_window(root: tk.Tk, width: int, height: int) -> None:
    """Center a Tk window on the active display."""
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")


def format_duration(seconds: float) -> str:
    """Format a duration for the statistics panel."""
    if seconds < 1.0:
        return f"{seconds * 1000.0:,.0f} ms"
    return f"{seconds:,.2f} s"


def format_order(order: Iterable[int], max_length: int = 34) -> str:
    """Format traversal order while keeping the UI compact."""
    text = " → ".join(str(node_id) for node_id in order)
    if len(text) <= max_length:
        return text or "—"
    return f"{text[: max_length - 1]}…"
