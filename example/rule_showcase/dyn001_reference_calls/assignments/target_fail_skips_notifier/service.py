"""Service layer that stores the order but never notifies."""

from __future__ import annotations

from typing import Any


class OrderService:
    def __init__(self, repository: Any, notifier: Any) -> None:
        self.repository = repository
        self.notifier = notifier

    def place(self, order_id: str, prices: list[float]) -> float:
        total = sum(prices)
        self.repository.save(order_id, total)
        return total
