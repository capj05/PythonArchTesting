"""Checkout service — target 2 (subtle mistakes).

Defect: ``checkout`` returns ``dict`` instead of ``Order``.
"""

from __future__ import annotations

from .contracts import OrderRepository
from .models import Cart, Order


class CheckoutService:
    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository

    def checkout(self, cart: Cart, customer: str) -> dict:
        order = Order.from_cart(cart, customer)
        saved = self._repository.save(order)
        return {"id": saved.id, "customer": saved.customer}
