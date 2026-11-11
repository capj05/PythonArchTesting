from __future__ import annotations

from .discounts import BulkDiscount, Discount, PercentDiscount


class PriceCalculator:
    def __init__(self, discount: Discount) -> None:
        self.discount = discount

    def total(self, prices: list[float]) -> float:
        if any(price < 0 for price in prices):
            raise ValueError("cena nesmí být záporná")
        amount = sum(prices)
        if isinstance(self.discount, PercentDiscount):
            amount = amount * (100 - self.discount.percent) / 100
        elif isinstance(self.discount, BulkDiscount):
            if amount >= self.discount.threshold:
                amount = amount * (100 - self.discount.percent) / 100
        else:
            amount = self.discount.apply(amount)
        return round(amount, 2)
