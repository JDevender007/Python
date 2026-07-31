"""Selection sort generator implementation."""

from collections.abc import Generator

from src.colors import Palette

SortFrame = tuple[list[int], list[str], int, int]


def selection_sort(values: list[int]) -> Generator[SortFrame, None, None]:
    """Yield visual states while sorting *values* with selection sort."""
    data = values.copy()
    length = len(data)
    comparisons = 0
    swaps = 0
    colors = [Palette.BAR] * length

    yield data.copy(), colors.copy(), comparisons, swaps

    for start in range(length - 1):
        minimum_index = start

        for current in range(start + 1, length):
            colors = [Palette.BAR] * length
            for sorted_index in range(start):
                colors[sorted_index] = Palette.SORTED
            colors[minimum_index] = Palette.ACCENT
            colors[current] = Palette.COMPARING
            comparisons += 1
            yield data.copy(), colors.copy(), comparisons, swaps

            if data[current] < data[minimum_index]:
                minimum_index = current
                colors[minimum_index] = Palette.ACCENT
                yield data.copy(), colors.copy(), comparisons, swaps

        if minimum_index != start:
            data[start], data[minimum_index] = data[minimum_index], data[start]
            swaps += 1
            colors = [Palette.BAR] * length
            for sorted_index in range(start):
                colors[sorted_index] = Palette.SORTED
            colors[start] = Palette.SWAPPING
            colors[minimum_index] = Palette.SWAPPING
            yield data.copy(), colors.copy(), comparisons, swaps

        colors = [Palette.BAR] * length
        for sorted_index in range(start + 1):
            colors[sorted_index] = Palette.SORTED
        yield data.copy(), colors.copy(), comparisons, swaps

    colors = [Palette.SORTED] * length
    yield data.copy(), colors.copy(), comparisons, swaps
