from .discounts import BulkDiscount, Discount, NoDiscount, PercentDiscount
from .pricing import PriceCalculator


def checkout(prices: list[float], code: str = "") -> float:
    if code == "STUDENT":
        discount = PercentDiscount(10)
    elif code == "VELKY_NAKUP":
        discount = BulkDiscount(1000, 5)
    else:
        discount = NoDiscount()
    calc = PriceCalculator(discount)
    return calc.total(prices)
