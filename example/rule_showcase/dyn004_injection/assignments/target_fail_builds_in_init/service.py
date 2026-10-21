"""Service that ignores the injected repository and builds its own.

The construction happens in ``__init__``, before ``place`` runs; the rule
watches the instance being built as well.
"""

from __future__ import annotations

from typing import Any

from .models import Order
from .repository import OrderRepository


class OrderService:
    def __init__(self, repository: Any = None) -> None:
        _ = repository
        self._repository = OrderRepository()

    def place(self, order_id: str, prices: list[float]) -> Order:
        order = Order(order_id, sum(prices))
        self._repository.save(order.order_id, order.total)
        return order
