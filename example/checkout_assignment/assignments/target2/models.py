"""Domain models — target 2 (subtle mistakes).

Defects:
* ``Product.__init__`` is missing the ``sku`` parameter — student took the value
  from a class default instead of accepting it at construction time.
* ``Order`` is missing the ``total`` attribute.
"""

from __future__ import annotations


class Product:
    def __init__(self, name: str, price: float) -> None:
        self.sku: str = "unknown"
        self.name: str = name
        self.price: float = price


class Cart:
    def __init__(self, items: list[tuple[Product, int]] | None = None) -> None:
        self._items: list[tuple[Product, int]] = list(items) if items else []

    @classmethod
    def empty(cls) -> Cart:
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
    def __init__(
        self,
        id: str,
        items: list[tuple[Product, int]],
        customer: str,
    ) -> None:
        self.id: str = id
        self.items: list[tuple[Product, int]] = items
        self.customer: str = customer

    @classmethod
    def from_cart(cls, cart: Cart, customer: str) -> Order:
        return cls(
            id=f"ord-{customer}",
            items=cart.items(),
            customer=customer,
        )
