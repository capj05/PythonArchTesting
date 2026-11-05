from __future__ import annotations


class Inventory:
    def __init__(self, stock: dict[str, int] | None = None) -> None:
        raise NotImplementedError

    def add(self, item: str, quantity: int) -> None:
        raise NotImplementedError

    def remove(self, item: str, quantity: int) -> None:
        raise NotImplementedError

    def quantity(self, item: str) -> int:
        raise NotImplementedError

    def items(self) -> dict[str, int]:
        raise NotImplementedError
