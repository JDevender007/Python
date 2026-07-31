"""Merge sort generator implementation."""

from collections.abc import Generator

from src.colors import Palette

SortFrame = tuple[list[int], list[str], int, int]


def merge_sort(values: list[int]) -> Generator[SortFrame, None, None]:
    """Yield visual states while sorting *values* with merge sort."""
    data = values.copy()
    length = len(data)
    comparisons = 0
    swaps = 0
    colors = [Palette.BAR] * length

    yield data.copy(), colors.copy(), comparisons, swaps

    def sort_range(left: int, right: int) -> Generator[SortFrame, None, None]:
        nonlocal comparisons, swaps
        if left >= right:
            return

        middle = (left + right) // 2
        yield from sort_range(left, middle)
        yield from sort_range(middle + 1, right)

        left_values = data[left : middle + 1]
        right_values = data[middle + 1 : right + 1]
        left_index = 0
        right_index = 0
        target = left

        while left_index < len(left_values) and right_index < len(right_values):
            colors = [Palette.BAR] * length
            for range_index in range(left, right + 1):
                colors[range_index] = Palette.ACCENT
            colors[left + left_index] = Palette.COMPARING
            colors[middle + 1 + right_index] = Palette.COMPARING
            comparisons += 1
            yield data.copy(), colors.copy(), comparisons, swaps

            if left_values[left_index] <= right_values[right_index]:
                data[target] = left_values[left_index]
                left_index += 1
            else:
                data[target] = right_values[right_index]
                right_index += 1
            swaps += 1
            colors[target] = Palette.SWAPPING
            yield data.copy(), colors.copy(), comparisons, swaps
            target += 1

        while left_index < len(left_values):
            data[target] = left_values[left_index]
            left_index += 1
            swaps += 1
            colors = [Palette.BAR] * length
            for range_index in range(left, right + 1):
                colors[range_index] = Palette.ACCENT
            colors[target] = Palette.SWAPPING
            yield data.copy(), colors.copy(), comparisons, swaps
            target += 1

        while right_index < len(right_values):
            data[target] = right_values[right_index]
            right_index += 1
            swaps += 1
            colors = [Palette.BAR] * length
            for range_index in range(left, right + 1):
                colors[range_index] = Palette.ACCENT
            colors[target] = Palette.SWAPPING
            yield data.copy(), colors.copy(), comparisons, swaps
            target += 1

    if length > 1:
        yield from sort_range(0, length - 1)

    colors = [Palette.SORTED] * length
    yield data.copy(), colors.copy(), comparisons, swaps
