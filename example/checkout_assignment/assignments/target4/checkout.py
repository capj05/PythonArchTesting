"""Checkout service — target 4 (renamed).

Defects:
* Class ``CheckoutService`` renamed to ``Checkout``.
* Method ``checkout`` renamed to ``process``.
"""

from __future__ import annotations

from .contracts import IOrderStore
from .models import Cart, Order


class Checkout:
    def __init__(self, store: IOrderStore) -> None:
        self._store = store

    def process(self, cart: Cart, customer: str) -> Order:
        order = Order.from_cart(cart, customer)
        return self._store.save(order)
