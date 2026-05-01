"""Checkout service — target 3."""

from __future__ import annotations

from .contracts import OrderRepository
from .models import Cart, Order


class CheckoutService:
    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository

    def checkout(self, cart: Cart, customer: str) -> Order:
        order = Order.from_cart(cart, customer)
        return self._repository.save(order)
