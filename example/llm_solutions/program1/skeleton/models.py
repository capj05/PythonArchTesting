"""Domain objects: an order changes only through its own methods."""

from __future__ import annotations


class Order:

    def __init__(self, order_id: str) -> None:
        raise NotImplementedError

    def add(self, price: float) -> None:
        raise NotImplementedError

    def apply_total(self, total: float) -> None:
        raise NotImplementedError

    def mark_placed(self) -> None:
        raise NotImplementedError
