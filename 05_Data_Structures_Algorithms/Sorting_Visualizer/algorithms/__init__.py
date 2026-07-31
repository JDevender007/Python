"""Sorting algorithm registry for the Sorting Visualizer application."""

from collections.abc import Callable, Generator
from typing import TypeAlias

from algorithms.bubble_sort import bubble_sort
from algorithms.heap_sort import heap_sort
from algorithms.insertion_sort import insertion_sort
from algorithms.merge_sort import merge_sort
from algorithms.quick_sort import quick_sort
from algorithms.selection_sort import selection_sort

SortFrame: TypeAlias = tuple[list[int], list[str], int, int]
SortGenerator: TypeAlias = Generator[SortFrame, None, None]
SortFunction: TypeAlias = Callable[[list[int]], SortGenerator]

ALGORITHMS: dict[str, SortFunction] = {
    "Bubble Sort": bubble_sort,
    "Selection Sort": selection_sort,
    "Insertion Sort": insertion_sort,
    "Merge Sort": merge_sort,
    "Quick Sort": quick_sort,
    "Heap Sort": heap_sort,
}

__all__ = [
    "ALGORITHMS",
    "SortFrame",
    "SortFunction",
    "SortGenerator",
    "bubble_sort",
    "selection_sort",
    "insertion_sort",
    "merge_sort",
    "quick_sort",
    "heap_sort",
]
