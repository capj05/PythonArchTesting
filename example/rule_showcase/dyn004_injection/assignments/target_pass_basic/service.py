"""Service that uses the injected repository, as the reference does."""

from __future__ import annotations

from typing import Any

from .models import Order


class OrderService:
    def __init__(self, repository: Any) -> None:
        self._repository = repository

    def place(self, order_id: str, prices: list[float]) -> Order:
        order = Order(order_id, sum(prices))
        self._repository.save(order.order_id, order.total)
        return order
