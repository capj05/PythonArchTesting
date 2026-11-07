from __future__ import annotations

from typing import Callable

Discount = Callable[[float], float]


def no_discount(amount: float) -> float:
    return amount


def percent_discount(percent: float) -> Discount:
    if not 0 <= percent <= 100:
        raise ValueError("sleva musí být mezi 0 a 100 %")

    def apply(amount: float) -> float:
        return amount * (100 - percent) / 100

    return apply


def bulk_discount(threshold: float, percent: float) -> Discount:
    if threshold < 0 or not 0 <= percent <= 100:
        raise ValueError("neplatná množstevní sleva")

    def apply(amount: float) -> float:
        if amount < threshold:
            return amount
        return amount * (100 - percent) / 100

    return apply
