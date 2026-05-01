"""Storage protocol — target 3."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .models import Order


class OrderRepository(Protocol):
    def save(self, order: Order) -> Order: ...
    def get(self, order_id: str) -> Order: ...
