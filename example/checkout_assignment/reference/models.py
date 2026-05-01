"""Domain models for the checkout assignment.

Demonstrates the API003 (``required_attribute``, ``required_constructor``)
and API004 (``required_factory``) rule families.
"""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import (
    required_attribute,
    required_constructor,
    required_factory,
)


class Product:
    """Catalog product. Constructor shape and instance attributes are part of the API."""

    __archtest__: Annotated[
        None,
        required_attribute("sku", annotation="str", storage="instance"),
        required_attribute("name", annotation="str", storage="instance"),
        required_attribute("price", annotation="float", storage="instance"),
        required_constructor(signature_mode="compatible"),
    ]

    def __init__(self, sku: str, name: str, price: float) -> None:
        self.sku: str = sku
        self.name: str = name
        self.price: float = price


class Cart:
    """Mutable cart of products. Provides an explicit ``empty()`` factory."""

    def __init__(self, items: list[tuple[Product, int]] | None = None) -> None:
        self._items: list[tuple[Product, int]] = list(items) if items else []

    @classmethod
    def empty(cls) -> Cart:
        __archtest__: Annotated[  # noqa: F842
            None,
            required_factory(
                satisfy_with=("classmethod",),
                name_match="exact",
                aliases=("empty",),
            ),
        ]
        return cls()

    def add_item(self, product: Product, quantity: int) -> None:
        self._items.append((product, quantity))

    def remove_item(self, sku: str) -> None:
        self._items = [(p, q) for p, q in self._items if p.sku != sku]

    def total(self) -> float:
        return sum(p.price * q for p, q in self._items)

    def items(self) -> list[tuple[Product, int]]:
        return list(self._items)


class Order:
    """Persisted order. Built from a ``Cart`` via ``Order.from_cart``."""

    __archtest__: Annotated[
        None,
        required_attribute("id", annotation="str", storage="instance"),
        required_attribute("items", storage="instance"),
        required_attribute("total", annotation="float", storage="instance"),
        required_attribute("customer", annotation="str", storage="instance"),
    ]

    def __init__(
        self,
        id: str,
        items: list[tuple[Product, int]],
        total: float,
        customer: str,
    ) -> None:
        self.id: str = id
        self.items: list[tuple[Product, int]] = items
        self.total: float = total
        self.customer: str = customer

    @classmethod
    def from_cart(cls, cart: Cart, customer: str) -> Order:
        __archtest__: Annotated[  # noqa: F842
            None,
            required_factory(
                satisfy_with=("classmethod",),
                name_match="exact",
                aliases=("from_cart",),
            ),
        ]
        return cls(
            id=f"ord-{customer}",
            items=cart.items(),
            total=cart.total(),
            customer=customer,
        )
