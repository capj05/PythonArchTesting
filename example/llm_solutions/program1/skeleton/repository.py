"""Storage layer."""

from __future__ import annotations
from typing import Any


class OrderRepository:

    def __init__(self) -> None:
        raise NotImplementedError

    def save(self, order: Any) -> None:
        raise NotImplementedError

    def get(self, order_id: str) -> Any:
        raise NotImplementedError
