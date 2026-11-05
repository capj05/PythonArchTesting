"""Shop operations: they work with the inventory only through its methods.

Each function may change the stock only by asking the inventory (``add``,
``remove``) and may read it only through ``quantity`` and ``items``. The
markers watch which code changes the inventory's attributes while the
functions run; what they compute is never compared.
"""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import forbid_foreign_writes

from .inventory import Inventory


def sell(inventory: Inventory, item: str, quantity: int) -> None:
    __archtest__: Annotated[  # noqa: F842
        None,
        forbid_foreign_writes(
            cases=[
                {"args": [{"$new": "inventory.Inventory", "args": [{"jablko": 5}]}, "jablko", 2]},
                {"args": [{"$new": "inventory.Inventory", "args": [{"jablko": 1}]}, "jablko", 3]},
            ],
        ),
    ]
    inventory.remove(item, quantity)


def restock(inventory: Inventory, deliveries: dict[str, int]) -> None:
    __archtest__: Annotated[  # noqa: F842
        None,
        forbid_foreign_writes(
            cases=[
                {"args": [{"$new": "inventory.Inventory", "args": [{"jablko": 1}]},
                          {"jablko": 4, "hruška": 2}]},
            ],
        ),
    ]
    for item, quantity in deliveries.items():
        inventory.add(item, quantity)


def clear_out(inventory: Inventory, item: str) -> int:
    __archtest__: Annotated[  # noqa: F842
        None,
        forbid_foreign_writes(
            cases=[
                {"args": [{"$new": "inventory.Inventory", "args": [{"jablko": 3, "hruška": 1}]},
                          "jablko"]},
            ],
        ),
    ]
    quantity = inventory.quantity(item)
    if quantity:
        inventory.remove(item, quantity)
    return quantity


def report(inventory: Inventory) -> str:
    __archtest__: Annotated[  # noqa: F842
        None,
        forbid_foreign_writes(
            cases=[
                {"args": [{"$new": "inventory.Inventory", "args": [{"jablko": 3, "hruška": 1}]}]},
            ],
        ),
    ]
    lines = [f"{item}: {count} ks" for item, count in sorted(inventory.items().items())]
    total = sum(inventory.items().values())
    return "\n".join(lines + [f"Celkem: {total} ks"])
