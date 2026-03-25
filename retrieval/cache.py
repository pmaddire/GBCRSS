"""In-memory retrieval cache."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RetrievalCache:
    _data: dict[str, tuple[str, ...]]

    def __init__(self) -> None:
        self._data = {}

    def get(self, key: str) -> tuple[str, ...] | None:
        return self._data.get(key)

    def set(self, key: str, value: tuple[str, ...]) -> None:
        self._data[key] = value

    def clear(self) -> None:
        self._data.clear()