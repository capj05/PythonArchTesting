from __future__ import annotations

from .discounts import Discount


class PriceCalculator:
    def __init__(self, discount: Discount) -> None:
        self.discount = discount

    def total(self, prices: list[float]) -> float:
        if any(price < 0 for price in prices):
            raise ValueError("cena nesmí být záporná")
        amount = sum(prices)
        return round(amount * 0.9, 2)
