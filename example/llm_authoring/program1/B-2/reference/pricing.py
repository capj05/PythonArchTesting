"""Discount strategies."""

from __future__ import annotations


class NoDiscount:
    def apply(self, total: float) -> float:
        return total


class PercentDiscount:
    def __init__(self, percent: float) -> None:
        self.percent = percent

    def apply(self, total: float) -> float:
        return round(total * (1 - self.percent / 100), 2)
