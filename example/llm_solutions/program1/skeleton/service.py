"""Application service: the only layer that talks to storage.

Its collaborators are injected, so nothing here imports the repository, the
discount strategies, or the event bus.
"""

from __future__ import annotations
from typing import Any
from .models import Order


class OrderService:

    def __init__(self, repository: Any, discount: Any, bus: Any) -> None:
        raise NotImplementedError

    def place(self, order_id: str, prices: list[float]) -> float:
        raise NotImplementedError
