from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Generic, TypeVar


T = TypeVar("T")


class IdentityRegistry(Generic[T]):
    """Insertion-ordered object registry with identity-based O(1) updates.

    CanvasCTk wrappers are frequently unhashable at the Tk compatibility
    layer, and equality is not the ownership relationship these registries
    represent.  Keying by ``id`` keeps membership and removal independent of
    user-defined equality while the stored value keeps that identity alive.
    """

    __slots__ = ("_items",)

    def __init__(self, values: Iterable[T] = ()) -> None:
        self._items: dict[int, T] = {}
        for value in values:
            self.add(value)

    def add(self, value: T) -> None:
        self._items.setdefault(id(value), value)

    append = add

    def discard(self, value: T) -> None:
        identity = id(value)
        if self._items.get(identity) is value:
            self._items.pop(identity, None)

    def remove(self, value: T) -> None:
        identity = id(value)
        if self._items.get(identity) is not value:
            raise ValueError(f"{value!r} is not in registry")
        del self._items[identity]

    def clear(self) -> None:
        self._items.clear()

    def __contains__(self, value: object) -> bool:
        return self._items.get(id(value)) is value

    def __iter__(self) -> Iterator[T]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)

    def snapshot(self) -> tuple[T, ...]:
        return tuple(self._items.values())


__all__ = ["IdentityRegistry"]
