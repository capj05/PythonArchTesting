from __future__ import annotations

from typing import Protocol


class Discount(Protocol):
    def apply(self, amount: float) -> float: ...


class NoDiscount:
    def apply(self, amount: float) -> float:
        return amount


class PercentDiscount:  # procentní sleva
    def __init__(self, percent: float) -> None:
        if not 0 <= percent <= 100:
            raise ValueError("sleva musí být mezi 0 a 100 %")
        self.percent = percent

    def apply(self, amount: float) -> float:
        return amount * (100 - self.percent) / 100


class BulkDiscount:
    def __init__(self, threshold: float, percent: float) -> None:
        if threshold < 0 or not 0 <= percent <= 100:
            raise ValueError("neplatná množstevní sleva")
        self.threshold = threshold
        self.percent = percent

    def apply(self, amount: float) -> float:
        if amount < self.threshold:
            return amount
        return amount * (100 - self.percent) / 100
