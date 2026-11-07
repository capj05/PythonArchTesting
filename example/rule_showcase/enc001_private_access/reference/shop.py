"""A report that reads the inventory through its public method."""

from typing import Annotated

from pythonarchtesting.rules import forbid_private_access

from .inventory import Inventory


def report(inventory: Inventory) -> str:
    __archtest__: Annotated[None, forbid_private_access()]
    return ", ".join(f"{k}: {v}" for k, v in sorted(inventory.items().items()))
