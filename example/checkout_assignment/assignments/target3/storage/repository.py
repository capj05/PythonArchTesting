"""In-memory order repository — target 3 (wrong dependencies).

Defects:
* Imports ``requests`` (forbidden in the storage package).
* ``save`` returns ``bool`` instead of ``Order`` — protocol violation.
"""

from __future__ import annotations

import requests  # noqa: F401  -- forbidden import

from ..models import Order


class InMemoryOrderRepository:
    def __init__(self) -> None:
        self._items: dict[str, Order] = {}

    def save(self, order: Order) -> bool:
        self._items[order.id] = order
        return True

    def get(self, order_id: str) -> Order:
        return self._items[order_id]
