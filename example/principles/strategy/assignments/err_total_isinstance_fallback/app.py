from __future__ import annotations

from .discounts import BulkDiscount, Discount, NoDiscount, PercentDiscount
from .pricing import PriceCalculator


def checkout(prices: list[float], code: str = "") -> float:
    discount: Discount
    if code == "STUDENT":
        discount = PercentDiscount(10)
    elif code == "VELKY_NAKUP":
        discount = BulkDiscount(1000, 5)
    else:
        discount = NoDiscount()
    return PriceCalculator(discount).total(prices)
