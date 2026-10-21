"""Service with other internals: no ``Order`` object, a dict instead.

It still only uses the repository it was given, so it passes.
"""

from __future__ import annotations

from typing import Any


class OrderService:
    def __init__(self, repository: Any) -> None:
        self._repository = repository

    def place(self, order_id: str, prices: list[float]) -> dict[str, Any]:
        record = {"order_id": order_id, "total": round(sum(prices), 2)}
        self._repository.save(record["order_id"], record["total"])
        return record
