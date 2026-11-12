from .discounts import BulkDiscount, Discount, NoDiscount, PercentDiscount
from .pricing import PriceCalculator


def checkout(prices: list[float], code: str = "") -> float:
    if code == "STUDENT":
        d = PercentDiscount(10)
    elif code == "VELKY_NAKUP":
        d = BulkDiscount(1000, 5)
    else:
        d = NoDiscount()
    calc = PriceCalculator(d)
    return calc.total(prices)
