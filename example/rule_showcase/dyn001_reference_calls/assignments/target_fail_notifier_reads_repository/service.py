"""Service layer that hands the repository to the notifier."""

from __future__ import annotations

from typing import Any


class OrderService:
    def __init__(self, repository: Any, notifier: Any) -> None:
        self.repository = repository
        self.notifier = notifier
        notifier.repository = repository

    def place(self, order_id: str, prices: list[float]) -> float:
        total = sum(prices)
        self.repository.save(order_id, total)
        self.notifier.order_placed(order_id, total)
        return total
