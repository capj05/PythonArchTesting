"""The report reads the inventory's private stock."""

from .inventory import Inventory


def report(inventory: Inventory) -> str:
    return ", ".join(f"{k}: {v}" for k, v in sorted(inventory._stock.items()))
