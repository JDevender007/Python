"""Quick sort generator implementation."""

from collections.abc import Generator

from src.colors import Palette

SortFrame = tuple[list[int], list[str], int, int]


def quick_sort(values: list[int]) -> Generator[SortFrame, None, None]:
    """Yield visual states while sorting *values* with quick sort."""
    data = values.copy()
    length = len(data)
    comparisons = 0
    swaps = 0
    colors = [Palette.BAR] * length
    fixed_positions: set[int] = set()

    yield data.copy(), colors.copy(), comparisons, swaps

    def partition(low: int, high: int) -> Generator[SortFrame, None, int]:
        nonlocal comparisons, swaps
        pivot = data[high]
        smaller = low - 1

        for current in range(low, high):
            colors = [Palette.BAR] * length
            for index in fixed_positions:
                colors[index] = Palette.SORTED
            colors[current] = Palette.COMPARING
            colors[high] = Palette.ACCENT
            comparisons += 1
            yield data.copy(), colors.copy(), comparisons, swaps

            if data[current] <= pivot:
                smaller += 1
                if smaller != current:
                    data[smaller], data[current] = data[current], data[smaller]
                    swaps += 1
                    colors[smaller] = Palette.SWAPPING
                    colors[current] = Palette.SWAPPING
                    yield data.copy(), colors.copy(), comparisons, swaps

        pivot_index = smaller + 1
        if pivot_index != high:
            data[pivot_index], data[high] = data[high], data[pivot_index]
            swaps += 1
        colors = [Palette.BAR] * length
        for index in fixed_positions:
            colors[index] = Palette.SORTED
        colors[pivot_index] = Palette.SWAPPING
        colors[high] = Palette.SWAPPING
        yield data.copy(), colors.copy(), comparisons, swaps
        return pivot_index

    def sort_range(low: int, high: int) -> Generator[SortFrame, None, None]:
        if low > high:
            return
        if low == high:
            fixed_positions.add(low)
            colors = [Palette.BAR] * length
            for index in fixed_positions:
                colors[index] = Palette.SORTED
            yield data.copy(), colors.copy(), comparisons, swaps
            return

        pivot_index = yield from partition(low, high)
        fixed_positions.add(pivot_index)
        colors = [Palette.BAR] * length
        for index in fixed_positions:
            colors[index] = Palette.SORTED
        yield data.copy(), colors.copy(), comparisons, swaps
        yield from sort_range(low, pivot_index - 1)
        yield from sort_range(pivot_index + 1, high)

    if length > 0:
        yield from sort_range(0, length - 1)

    colors = [Palette.SORTED] * length
    yield data.copy(), colors.copy(), comparisons, swaps
