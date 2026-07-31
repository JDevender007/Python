"""Complexity metadata for supported sorting algorithms."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComplexityInfo:
    """Time and space complexity information for one algorithm."""

    best: str
    average: str
    worst: str
    space: str


COMPLEXITIES: dict[str, ComplexityInfo] = {
    "Bubble Sort": ComplexityInfo("O(n)", "O(n²)", "O(n²)", "O(1)"),
    "Selection Sort": ComplexityInfo("O(n²)", "O(n²)", "O(n²)", "O(1)"),
    "Insertion Sort": ComplexityInfo("O(n)", "O(n²)", "O(n²)", "O(1)"),
    "Merge Sort": ComplexityInfo("O(n log n)", "O(n log n)", "O(n log n)", "O(n)"),
    "Quick Sort": ComplexityInfo("O(n log n)", "O(n log n)", "O(n²)", "O(log n)"),
    "Heap Sort": ComplexityInfo("O(n log n)", "O(n log n)", "O(n log n)", "O(1)"),
}


def get_complexity(algorithm_name: str) -> ComplexityInfo:
    """Return complexity metadata for *algorithm_name*."""
    try:
        return COMPLEXITIES[algorithm_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported algorithm: {algorithm_name}") from exc
