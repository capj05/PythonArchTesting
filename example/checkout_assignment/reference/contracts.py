"""Storage protocol for the checkout assignment.

This module defines the persistence contract that any concrete order
repository must satisfy. The protocol itself carries no rule markers;
implementing classes declare ``implements_protocol(OrderRepository, ...)``.
"""

from __future__ import annotations

from typing import Protocol

from .models import Order


class OrderRepository(Protocol):
    """Persistence API for stored orders."""

    def save(self, order: Order) -> Order:
        """Persist an order and return the stored copy."""

    def get(self, order_id: str) -> Order:
        """Load a previously saved order by id."""
