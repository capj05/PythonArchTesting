"""Notification layer: formats messages; knows nothing about storage."""

from __future__ import annotations


class Notifier:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def order_placed(self, order_id: str, total: float) -> None:
        self.sent.append(f"order {order_id}: {total:.2f}")
