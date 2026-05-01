"""Target 3: working but with the wrong dependencies."""

from .checkout import CheckoutService
from .contracts import OrderRepository
from .models import Cart, Order, Product
from .storage import InMemoryOrderRepository

__all__ = [
    "Cart",
    "CheckoutService",
    "InMemoryOrderRepository",
    "Order",
    "OrderRepository",
    "Product",
]
