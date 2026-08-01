"""Capacity-limited generic stack implementation."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Generic, TypeVar

from .utils import StructureOverflowError, StructureUnderflowError


T = TypeVar("T")


class Stack(Generic[T]):
    """A last-in, first-out data structure with fixed capacity."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("Stack capacity must be greater than zero.")
        self._capacity = capacity
        self._items: list[T] = []

    @property
    def capacity(self) -> int:
        """Return the maximum number of elements."""

        return self._capacity

    @property
    def size(self) -> int:
        """Return the number of stored elements."""

        return len(self._items)

    @property
    def is_empty(self) -> bool:
        """Return whether the stack contains no elements."""

        return not self._items

    @property
    def is_full(self) -> bool:
        """Return whether the stack has reached capacity."""

        return self.size >= self.capacity

    def push(self, item: T) -> None:
        """Place an item on top of the stack."""

        if self.is_full:
            raise StructureOverflowError(
                f"Stack overflow: maximum capacity is {self.capacity}."
            )
        self._items.append(item)

    def pop(self) -> T:
        """Remove and return the top item."""

        if self.is_empty:
            raise StructureUnderflowError("Stack underflow: the stack is empty.")
        return self._items.pop()

    def peek(self) -> T:
        """Return the top item without removing it."""

        if self.is_empty:
            raise StructureUnderflowError("Stack underflow: the stack is empty.")
        return self._items[-1]

    def clear(self) -> None:
        """Remove every item from the stack."""

        self._items.clear()

    def to_list(self) -> list[T]:
        """Return a bottom-to-top copy of the stack contents."""

        return self._items.copy()

    def __len__(self) -> int:
        return self.size

    def __iter__(self) -> Iterator[T]:
        return iter(self._items)

    def __repr__(self) -> str:
        return f"Stack(capacity={self.capacity}, items={self._items!r})"
