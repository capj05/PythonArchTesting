"""Checkout service.

Demonstrates the API001 (``required_entity_signature``) and API002
(``required_method``) rule families.
"""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import required_entity_signature, required_method

from .contracts import OrderRepository
from .models import Cart, Order


class CheckoutService:
    """Convert a cart into a stored order."""

    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository

    def checkout(
        self,
        cart: Cart,
        customer: str,
    ) -> Annotated[
        Order,
        required_entity_signature(mode="compatible", return_annotation="error"),
    ]:
        __archtest__: Annotated[  # noqa: F842
            None,
            required_method(signature_mode="compatible"),
        ]
        order = Order.from_cart(cart, customer)
        return self._repository.save(order)
