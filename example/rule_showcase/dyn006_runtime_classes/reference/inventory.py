"""Reference module for the DYN006/DYN007 runtime class showcase.

Three class contracts that depend on what Python builds at run time:

- ``Inventory`` derives from ``collections.abc.MutableMapping``. Which
  abstract methods it must implement is defined by the standard library, so
  only Python can tell whether it is instantiable: ``is_runtime_concrete_class``.
- ``Storage`` is a base that must stay abstract (``is_runtime_abstract_class``),
  whatever it inherits.
- ``CsvExporter`` must satisfy the ``Exporter`` protocol on its instances
  (``implements_runtime_protocol``): a ``name`` and an ``export(rows)`` method,
  wherever they come from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, MutableMapping
from typing import Annotated, Protocol

from pythonarchtesting.rules import (
    implements_runtime_protocol,
    is_runtime_abstract_class,
    is_runtime_concrete_class,
)


class Exporter(Protocol):
    name: str

    def export(self, rows: list[dict[str, str]]) -> str: ...


class Inventory(MutableMapping[str, int]):
    __archtest__: Annotated[None, is_runtime_concrete_class(cases=[{"args": []}])]

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
    __archtest__: Annotated[None, is_runtime_abstract_class()]

    @abstractmethod
    def save(self, inventory: Inventory) -> None: ...


class CsvExporter:
    __archtest__: Annotated[
        None,
        implements_runtime_protocol(Exporter, cases=[{"args": [";"]}]),
    ]

    name = "csv"

    def __init__(self, separator: str) -> None:
        self.separator = separator

    def export(self, rows: list[dict[str, str]]) -> str:
        return "\n".join(self.separator.join(row.values()) for row in rows)
