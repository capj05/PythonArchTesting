from __future__ import annotations

from .inventory import Inventory


def sell(inventory: Inventory, item: str, quantity: int) -> None:
    raise NotImplementedError


def restock(inventory: Inventory, deliveries: dict[str, int]) -> None:
    raise NotImplementedError


def clear_out(inventory: Inventory, item: str) -> int:
    raise NotImplementedError


def report(inventory: Inventory) -> str:
    raise NotImplementedError
