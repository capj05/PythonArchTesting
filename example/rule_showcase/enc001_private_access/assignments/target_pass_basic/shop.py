"""A report that reads the inventory through its public method."""

from .inventory import Inventory


def report(inventory: Inventory) -> str:
    return ", ".join(f"{k}: {v}" for k, v in sorted(inventory.items().items()))
