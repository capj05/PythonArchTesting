"""Service layer: business operations, delegating storage to the repository."""

from __future__ import annotations

from typing import Any


class OrderService:
    def __init__(self, repository: Any) -> None:
        self._repository = repository

    def place(self, order_id: str, prices: list[float]) -> float:
        total = sum(prices)
        self._repository.save(order_id, total)
        return total
