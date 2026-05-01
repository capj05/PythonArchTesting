"""In-memory order repository.

Demonstrates the PRO001 (``implements_protocol``) rule family.
"""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import implements_protocol

from ..contracts import OrderRepository
from ..models import Order


class InMemoryOrderRepository:
    """Repository implementation that satisfies ``OrderRepository``."""

    __archtest__: Annotated[
        None,
        implements_protocol(
            OrderRepository,
            signature_mode="compatible",
            return_annotation="error",
        ),
    ]

    def __init__(self) -> None:
        self._items: dict[str, Order] = {}

    def save(self, order: Order) -> Order:
        self._items[order.id] = order
        return order

    def get(self, order_id: str) -> Order:
        return self._items[order_id]
