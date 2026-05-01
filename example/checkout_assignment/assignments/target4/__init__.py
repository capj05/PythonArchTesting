"""Target 4: working code, renamed to a different style."""

from .checkout import Checkout
from .contracts import IOrderStore
from .models import Cart, Order, Product
from .storage import InMemoryStore

__all__ = [
    "Cart",
    "Checkout",
    "IOrderStore",
    "InMemoryStore",
    "Order",
    "Product",
]
