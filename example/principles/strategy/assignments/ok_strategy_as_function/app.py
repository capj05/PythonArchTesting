from __future__ import annotations

from .discounts import Discount, bulk_discount, no_discount, percent_discount
from .pricing import PriceCalculator


def checkout(prices: list[float], code: str = "") -> float:
    discount: Discount
    if code == "STUDENT":
        discount = percent_discount(10)
    elif code == "VELKY_NAKUP":
        discount = bulk_discount(1000, 5)
    else:
        discount = no_discount
    return PriceCalculator(discount).total(prices)
