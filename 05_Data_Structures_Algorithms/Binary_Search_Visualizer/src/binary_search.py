"""Generator-based search algorithm implementations."""

from __future__ import annotations

from collections.abc import Generator, Sequence
from typing import TypeAlias

from .config import PALETTE

SearchStep: TypeAlias = tuple[
    list[int],
    list[str],
    int,
    int,
    int,
    int,
    int,
]
SearchGenerator: TypeAlias = Generator[SearchStep, None, None]


def _base_colors(array: Sequence[int]) -> list[str]:
    """Create a default color list matching the array length."""

    return [PALETTE.default_bar] * len(array)


def binary_search_steps(array: Sequence[int], target: int) -> SearchGenerator:
    """Yield each state of a binary search over an ascending array.

    Every yielded value is a seven-item tuple containing an array copy, color
    copy, left index, right index, middle index, current index, and comparison
    count.
    """

    values = sorted(array)
    left = 0
    right = len(values) - 1
    comparisons = 0

    while left <= right:
        middle = (left + right) // 2
        comparisons += 1
        colors = _base_colors(values)
        colors[left] = PALETTE.left_boundary
        colors[right] = PALETTE.right_boundary
        colors[middle] = PALETTE.middle_element

        yield (
            values.copy(),
            colors.copy(),
            left,
            right,
            middle,
            middle,
            comparisons,
        )

        if values[middle] == target:
            colors[middle] = PALETTE.found_element
            yield (
                values.copy(),
                colors.copy(),
                left,
                right,
                middle,
                middle,
                comparisons,
            )
            return

        if values[middle] < target:
            left = middle + 1
        else:
            right = middle - 1

    colors = [PALETTE.not_found] * len(values)
    yield (
        values.copy(),
        colors.copy(),
        left,
        right,
        -1,
        -1,
        comparisons,
    )


def linear_search_steps(array: Sequence[int], target: int) -> SearchGenerator:
    """Yield each state of a left-to-right linear search."""

    values = list(array)
    comparisons = 0
    right = len(values) - 1

    for current_index, value in enumerate(values):
        comparisons += 1
        colors = _base_colors(values)
        colors[0] = PALETTE.left_boundary
        colors[right] = PALETTE.right_boundary
        colors[current_index] = PALETTE.current_element

        yield (
            values.copy(),
            colors.copy(),
            0,
            right,
            -1,
            current_index,
            comparisons,
        )

        if value == target:
            colors[current_index] = PALETTE.found_element
            yield (
                values.copy(),
                colors.copy(),
                0,
                right,
                -1,
                current_index,
                comparisons,
            )
            return

    colors = [PALETTE.not_found] * len(values)
    yield (
        values.copy(),
        colors.copy(),
        0 if values else -1,
        right,
        -1,
        -1,
        comparisons,
    )
