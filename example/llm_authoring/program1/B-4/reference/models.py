"""Domain objects: an order changes only through its own methods."""

from __future__ import annotations




class Order:
    def __init__(self, order_id: str) -> None:
        self.order_id = order_id
        self.items: list[float] = []
        self.total = 0.0
        self.status = "new"

    def add(self, price: float) -> None:
        self.items.append(price)
        self.total += price

    def apply_total(self, total: float) -> None:
        self.total = total

    def mark_placed(self) -> None:
        self.status = "placed"
