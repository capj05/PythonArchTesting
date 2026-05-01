"""Storage protocol — target 1."""

from __future__ import annotations

from typing import Protocol

from .models import Order


class OrderRepository(Protocol):
    def save(self, order: Order) -> Order: ...
    def get(self, order_id: str) -> Order: ...
