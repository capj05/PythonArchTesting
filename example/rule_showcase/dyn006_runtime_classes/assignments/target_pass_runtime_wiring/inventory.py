"""Members provided at run time.

``Inventory`` gets ``__len__`` from a mixin, and ``CsvExporter`` binds
``export`` and sets ``name`` in ``__init__``; a static reading of the class
body finds neither."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, MutableMapping


class _Sized:
    def __len__(self) -> int:
        return len(self._items)  # type: ignore[attr-defined]


class Inventory(_Sized, MutableMapping):
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



class Storage(ABC):
    @abstractmethod
    def save(self, inventory: Inventory) -> None: ...


class CsvExporter:
    def __init__(self, separator: str) -> None:
        self.separator = separator
        self.name = "csv"
        self.export = self._to_csv

    def _to_csv(self, rows: list[dict[str, str]]) -> str:
        return "\n".join(self.separator.join(row.values()) for row in rows)
