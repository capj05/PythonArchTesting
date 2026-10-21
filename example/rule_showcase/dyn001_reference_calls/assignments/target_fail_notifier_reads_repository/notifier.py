"""Notification layer that looks the total up in storage itself."""

from __future__ import annotations

from typing import Any


class Notifier:
    def __init__(self, repository: Any = None) -> None:
        self.sent: list[str] = []
        self.repository = repository

    def order_placed(self, order_id: str, total: float) -> None:
        stored = self.repository.get(order_id) if self.repository else total
        self.sent.append(f"order {order_id}: {stored:.2f}")
