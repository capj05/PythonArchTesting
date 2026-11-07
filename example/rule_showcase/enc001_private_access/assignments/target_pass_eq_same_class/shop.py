"""The report compares with an empty inventory through ``==``."""

from .inventory import Inventory


def report(inventory: Inventory) -> str:
    if inventory == Inventory({}):
        return "empty"
    return ", ".join(f"{k}: {v}" for k, v in sorted(inventory.items().items()))
