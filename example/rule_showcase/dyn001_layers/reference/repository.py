"""Storage layer: only the service layer may call it."""

from __future__ import annotations


class OrderRepository:
    def __init__(self) -> None:
        self._totals: dict[str, float] = {}

    def save(self, order_id: str, total: float) -> None:
        self._totals[order_id] = total

    def get(self, order_id: str) -> float | None:
        return self._totals.get(order_id)
