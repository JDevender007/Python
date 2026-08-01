"""Shared utility helpers and application-specific exceptions."""

from __future__ import annotations

import random
from collections.abc import Iterable
from typing import TypeVar


T = TypeVar("T", int, float)


class DataStructureError(Exception):
    """Base exception for data-structure operation failures."""


class StructureOverflowError(DataStructureError):
    """Raised when inserting into a full data structure."""


class StructureUnderflowError(DataStructureError):
    """Raised when removing or reading from an empty data structure."""


class InputValidationError(ValueError):
    """Raised when element input is invalid."""


def clamp(value: T, minimum: T, maximum: T) -> T:
    """Clamp a numeric value to an inclusive range."""

    return max(minimum, min(maximum, value))


def lerp(start: float, end: float, progress: float) -> float:
    """Linearly interpolate between two values."""

    return start + (end - start) * progress


def ease_in_out_cubic(progress: float) -> float:
    """Apply a smooth cubic ease-in-out curve."""

    if progress < 0.5:
        return 4 * progress * progress * progress
    return 1 - pow(-2 * progress + 2, 3) / 2


def validate_element(raw_value: str, maximum_length: int) -> str:
    """Normalize and validate an element entered by the user."""

    value = raw_value.strip()
    if not value:
        raise InputValidationError("Enter an element before performing this operation.")
    if len(value) > maximum_length:
        raise InputValidationError(
            f"Elements are limited to {maximum_length} characters."
        )
    return value


def generate_random_values(
    count: int,
    minimum: int,
    maximum: int,
) -> list[str]:
    """Return a list of random integer values represented as strings."""

    return [str(random.randint(minimum, maximum)) for _ in range(count)]


def shorten_text(value: object, maximum_length: int = 14) -> str:
    """Return a compact display form of a value."""

    text = str(value)
    if len(text) <= maximum_length:
        return text
    return f"{text[: maximum_length - 1]}…"


def describe_values(values: Iterable[object]) -> str:
    """Return a readable comma-separated representation of values."""

    return ", ".join(str(value) for value in values)
