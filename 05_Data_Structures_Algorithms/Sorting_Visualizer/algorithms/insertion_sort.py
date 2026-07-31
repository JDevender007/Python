"""Insertion sort generator implementation."""

from collections.abc import Generator

from src.colors import Palette

SortFrame = tuple[list[int], list[str], int, int]


def insertion_sort(values: list[int]) -> Generator[SortFrame, None, None]:
    """Yield visual states while sorting *values* with insertion sort."""
    data = values.copy()
    length = len(data)
    comparisons = 0
    swaps = 0
    colors = [Palette.BAR] * length

    yield data.copy(), colors.copy(), comparisons, swaps

    for current in range(1, length):
        key = data[current]
        position = current - 1
        colors = [Palette.BAR] * length
        colors[current] = Palette.ACCENT
        yield data.copy(), colors.copy(), comparisons, swaps

        while position >= 0:
            colors = [Palette.BAR] * length
            colors[position] = Palette.COMPARING
            colors[position + 1] = Palette.ACCENT
            comparisons += 1
            yield data.copy(), colors.copy(), comparisons, swaps

            if data[position] <= key:
                break

            data[position + 1] = data[position]
            swaps += 1
            colors[position] = Palette.SWAPPING
            colors[position + 1] = Palette.SWAPPING
            yield data.copy(), colors.copy(), comparisons, swaps
            position -= 1

        data[position + 1] = key
        colors = [Palette.BAR] * length
        for sorted_index in range(current + 1):
            colors[sorted_index] = Palette.ACCENT
        colors[position + 1] = Palette.SWAPPING
        yield data.copy(), colors.copy(), comparisons, swaps

    colors = [Palette.SORTED] * length
    yield data.copy(), colors.copy(), comparisons, swaps
