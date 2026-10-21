"""Service layer with its own pricing: totals are rounded to whole units."""

from __future__ import annotations

from typing import Any


class OrderService:
    def __init__(self, repository: Any) -> None:
        self._repository = repository

    def place(self, order_id: str, prices: list[float]) -> float:
        total = float(round(sum(prices)))
        self._repository.save(order_id, total)
        return total
