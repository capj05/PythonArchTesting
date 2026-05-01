"""Storage protocol — target 4 (renamed).

Defect: protocol class renamed ``OrderRepository`` → ``IOrderStore``. The
matcher should produce a low-confidence match or leave the rule unmatched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .models import Order


class IOrderStore(Protocol):
    def save(self, order: Order) -> Order: ...
    def get(self, order_id: str) -> Order: ...
