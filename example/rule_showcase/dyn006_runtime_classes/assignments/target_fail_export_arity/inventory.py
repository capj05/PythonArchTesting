"""``export`` takes no rows: it exists, but cannot be called as the
protocol says."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, MutableMapping


class Inventory(MutableMapping):
    def __init__(self) -> None:
        self._items: dict[str, int] = {}

    def __getitem__(self, key: str) -> int:
        return self._items[key]

    def __setitem__(self, key: str, value: int) -> None:
        self._items[key] = value

    def __delitem__(self, key: str) -> None:
        del self._items[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


class Storage(ABC):
    @abstractmethod
    def save(self, inventory: Inventory) -> None: ...


class CsvExporter:
    name = "csv"

    def __init__(self, separator: str) -> None:
        self.separator = separator
        self.rows: list[dict[str, str]] = []

    def export(self) -> str:
        return "\n".join(self.separator.join(row.values()) for row in self.rows)
