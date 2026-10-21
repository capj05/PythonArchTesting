"""Service that creates a fresh repository on every call."""

from __future__ import annotations

from typing import Any

from .models import Order
from .repository import OrderRepository


class OrderService:
    def __init__(self, repository: Any) -> None:
        self._repository = repository

    def place(self, order_id: str, prices: list[float]) -> Order:
        order = Order(order_id, sum(prices))
        OrderRepository().save(order.order_id, order.total)
        return order
