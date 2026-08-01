"""Capacity-limited generic queue implementation."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from typing import Deque, Generic, TypeVar

from .utils import StructureOverflowError, StructureUnderflowError


T = TypeVar("T")


class Queue(Generic[T]):
    """A first-in, first-out data structure with fixed capacity."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("Queue capacity must be greater than zero.")
        self._capacity = capacity
        self._items: Deque[T] = deque()

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
        """Return whether the queue contains no elements."""

        return not self._items

    @property
    def is_full(self) -> bool:
        """Return whether the queue has reached capacity."""

        return self.size >= self.capacity

    def enqueue(self, item: T) -> None:
        """Add an item to the rear of the queue."""

        if self.is_full:
            raise StructureOverflowError(
                f"Queue overflow: maximum capacity is {self.capacity}."
            )
        self._items.append(item)

    def dequeue(self) -> T:
        """Remove and return the front item."""

        if self.is_empty:
            raise StructureUnderflowError("Queue underflow: the queue is empty.")
        return self._items.popleft()

    def front(self) -> T:
        """Return the front item without removing it."""

        if self.is_empty:
            raise StructureUnderflowError("Queue underflow: the queue is empty.")
        return self._items[0]

    def rear(self) -> T:
        """Return the rear item without removing it."""

        if self.is_empty:
            raise StructureUnderflowError("Queue underflow: the queue is empty.")
        return self._items[-1]

    def clear(self) -> None:
        """Remove every item from the queue."""

        self._items.clear()

    def to_list(self) -> list[T]:
        """Return a front-to-rear copy of the queue contents."""

        return list(self._items)

    def __len__(self) -> int:
        return self.size

    def __iter__(self) -> Iterator[T]:
        return iter(self._items)

    def __repr__(self) -> str:
        return f"Queue(capacity={self.capacity}, items={list(self._items)!r})"
