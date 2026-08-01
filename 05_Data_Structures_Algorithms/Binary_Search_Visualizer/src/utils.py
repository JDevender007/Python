"""Reusable utility functions for data generation and animation."""

from __future__ import annotations

import random
import re
from collections.abc import Iterable

from .config import MAX_ARRAY_VALUE, MIN_ARRAY_VALUE


class InputValidationError(ValueError):
    """Raised when user-provided array or target data is invalid."""


def generate_sorted_array(
    size: int,
    minimum: int = MIN_ARRAY_VALUE,
    maximum: int = MAX_ARRAY_VALUE,
) -> list[int]:
    """Return a sorted random integer array of the requested size."""

    if size <= 0:
        raise ValueError("Array size must be positive.")
    if minimum > maximum:
        raise ValueError("Minimum value cannot exceed maximum value.")
    return sorted(random.randint(minimum, maximum) for _ in range(size))


def parse_custom_array(raw_value: str, maximum_items: int = 200) -> list[int]:
    """Parse comma or whitespace-separated integers and return a sorted list.

    Args:
        raw_value: Text entered by the user.
        maximum_items: Safety limit for the number of values accepted.

    Raises:
        InputValidationError: If the input is empty, invalid, or too large.
    """

    cleaned = raw_value.strip()
    if not cleaned:
        raise InputValidationError("Enter at least one integer.")

    tokens = [token for token in re.split(r"[\s,;]+", cleaned) if token]
    if len(tokens) > maximum_items:
        raise InputValidationError(
            f"Custom arrays are limited to {maximum_items} values."
        )

    try:
        values = [int(token) for token in tokens]
    except ValueError as exc:
        raise InputValidationError(
            "Use integers separated by commas or spaces."
        ) from exc

    if not values:
        raise InputValidationError("Enter at least one integer.")
    return sorted(values)


def validate_search_target(raw_value: str) -> int:
    """Parse and validate a search target integer."""

    cleaned = raw_value.strip()
    if not cleaned:
        raise InputValidationError("Enter a search value.")
    try:
        return int(cleaned)
    except ValueError as exc:
        raise InputValidationError("Search value must be an integer.") from exc


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a numeric value to the inclusive range provided."""

    return max(minimum, min(maximum, value))


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Convert a #RRGGBB color string to an RGB tuple."""

    normalized = color.lstrip("#")
    if len(normalized) != 6:
        raise ValueError(f"Invalid color value: {color}")
    return tuple(int(normalized[index : index + 2], 16) for index in (0, 2, 4))


def rgb_to_hex(red: int, green: int, blue: int) -> str:
    """Convert RGB channel values to a #RRGGBB color string."""

    channels = (red, green, blue)
    bounded = (int(clamp(channel, 0, 255)) for channel in channels)
    return "#{:02X}{:02X}{:02X}".format(*bounded)


def interpolate_color(start: str, end: str, progress: float) -> str:
    """Interpolate between two hexadecimal colors."""

    fraction = clamp(progress, 0.0, 1.0)
    start_rgb = hex_to_rgb(start)
    end_rgb = hex_to_rgb(end)
    channels = tuple(
        round(first + (second - first) * fraction)
        for first, second in zip(start_rgb, end_rgb, strict=True)
    )
    return rgb_to_hex(*channels)


def ensure_color_count(colors: Iterable[str], count: int, fallback: str) -> list[str]:
    """Return exactly ``count`` colors, padding or trimming as required."""

    normalized = list(colors)[:count]
    if len(normalized) < count:
        normalized.extend([fallback] * (count - len(normalized)))
    return normalized
