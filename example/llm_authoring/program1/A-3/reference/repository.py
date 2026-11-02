"""Storage layer."""

from __future__ import annotations

from typing import Any


class OrderRepository:
    def __init__(self) -> None:
        self._rows: dict[str, Any] = {}

    def save(self, order: Any) -> None:
        self._rows[order.order_id] = order

    def get(self, order_id: str) -> Any:
        return self._rows.get(order_id)
