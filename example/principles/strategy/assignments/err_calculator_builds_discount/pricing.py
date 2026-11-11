from __future__ import annotations

from .discounts import Discount, PercentDiscount


class PriceCalculator:
    def __init__(self, discount: Discount) -> None:
        self.discount = PercentDiscount(10)

    def total(self, prices: list[float]) -> float:
        if any(price < 0 for price in prices):
            raise ValueError("cena nesmí být záporná")
        amount = sum(prices)
        return round(self.discount.apply(amount), 2)
