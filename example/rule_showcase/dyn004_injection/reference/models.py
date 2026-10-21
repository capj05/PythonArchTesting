"""Domain objects the service may create freely."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Order:
    order_id: str
    total: float
