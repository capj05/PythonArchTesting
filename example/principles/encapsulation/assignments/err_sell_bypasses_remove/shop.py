"""Shop operations."""

from __future__ import annotations

from .inventory import Inventory


def sell(inventory: Inventory, item: str, quantity: int) -> None:
    if inventory._stock.get(item, 0) >= quantity:
        inventory._stock[item] -= quantity


def restock(inventory: Inventory, deliveries: dict[str, int]) -> None:
    for item, quantity in deliveries.items():
        inventory.add(item, quantity)


def clear_out(inventory: Inventory, item: str) -> int:
    quantity = inventory.quantity(item)
    if quantity:
        inventory.remove(item, quantity)
    return quantity


def report(inventory: Inventory) -> str:
    lines = [f"{item}: {count} ks" for item, count in sorted(inventory.items().items())]
    total = sum(inventory.items().values())
    return "\n".join(lines + [f"Celkem: {total} ks"])
