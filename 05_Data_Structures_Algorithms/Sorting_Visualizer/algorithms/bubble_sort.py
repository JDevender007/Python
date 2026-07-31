"""Bubble sort generator implementation."""

from collections.abc import Generator

from src.colors import Palette

SortFrame = tuple[list[int], list[str], int, int]


def bubble_sort(values: list[int]) -> Generator[SortFrame, None, None]:
    """Yield visual states while sorting *values* with bubble sort."""
    data = values.copy()
    length = len(data)
    comparisons = 0
    swaps = 0
    colors = [Palette.BAR] * length

    yield data.copy(), colors.copy(), comparisons, swaps

    for end in range(length - 1, 0, -1):
        swapped = False
        for index in range(end):
            colors = [Palette.BAR] * length
            for sorted_index in range(end + 1, length):
                colors[sorted_index] = Palette.SORTED
            colors[index] = Palette.COMPARING
            colors[index + 1] = Palette.COMPARING
            comparisons += 1
            yield data.copy(), colors.copy(), comparisons, swaps

            if data[index] > data[index + 1]:
                data[index], data[index + 1] = data[index + 1], data[index]
                swaps += 1
                swapped = True
                colors[index] = Palette.SWAPPING
                colors[index + 1] = Palette.SWAPPING
                yield data.copy(), colors.copy(), comparisons, swaps

        colors = [Palette.BAR] * length
        for sorted_index in range(end, length):
            colors[sorted_index] = Palette.SORTED
        yield data.copy(), colors.copy(), comparisons, swaps

        if not swapped:
            break

    colors = [Palette.SORTED] * length
    yield data.copy(), colors.copy(), comparisons, swaps
