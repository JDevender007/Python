"""Heap sort generator implementation."""

from collections.abc import Generator

from src.colors import Palette

SortFrame = tuple[list[int], list[str], int, int]


def heap_sort(values: list[int]) -> Generator[SortFrame, None, None]:
    """Yield visual states while sorting *values* with heap sort."""
    data = values.copy()
    length = len(data)
    comparisons = 0
    swaps = 0
    colors = [Palette.BAR] * length
    sorted_start = length

    yield data.copy(), colors.copy(), comparisons, swaps

    def heapify(heap_size: int, root: int) -> Generator[SortFrame, None, None]:
        nonlocal comparisons, swaps
        current_root = root

        while True:
            largest = current_root
            left_child = 2 * current_root + 1
            right_child = 2 * current_root + 2

            if left_child < heap_size:
                colors = [Palette.BAR] * length
                for index in range(sorted_start, length):
                    colors[index] = Palette.SORTED
                colors[largest] = Palette.COMPARING
                colors[left_child] = Palette.COMPARING
                comparisons += 1
                yield data.copy(), colors.copy(), comparisons, swaps
                if data[left_child] > data[largest]:
                    largest = left_child

            if right_child < heap_size:
                colors = [Palette.BAR] * length
                for index in range(sorted_start, length):
                    colors[index] = Palette.SORTED
                colors[largest] = Palette.COMPARING
                colors[right_child] = Palette.COMPARING
                comparisons += 1
                yield data.copy(), colors.copy(), comparisons, swaps
                if data[right_child] > data[largest]:
                    largest = right_child

            if largest == current_root:
                return

            data[current_root], data[largest] = data[largest], data[current_root]
            swaps += 1
            colors = [Palette.BAR] * length
            for index in range(sorted_start, length):
                colors[index] = Palette.SORTED
            colors[current_root] = Palette.SWAPPING
            colors[largest] = Palette.SWAPPING
            yield data.copy(), colors.copy(), comparisons, swaps
            current_root = largest

    for root in range(length // 2 - 1, -1, -1):
        yield from heapify(length, root)

    for end in range(length - 1, 0, -1):
        data[0], data[end] = data[end], data[0]
        swaps += 1
        sorted_start = end
        colors = [Palette.BAR] * length
        for index in range(sorted_start, length):
            colors[index] = Palette.SORTED
        colors[0] = Palette.SWAPPING
        colors[end] = Palette.SWAPPING
        yield data.copy(), colors.copy(), comparisons, swaps
        yield from heapify(end, 0)

    colors = [Palette.SORTED] * length
    yield data.copy(), colors.copy(), comparisons, swaps
