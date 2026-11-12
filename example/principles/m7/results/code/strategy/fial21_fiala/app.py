from .discounts import BulkDiscount, Discount, NoDiscount, PercentDiscount
from .pricing import PriceCalculator


def checkout(prices: list[float], code: str = "") -> float:
    if code == "STUDENT":
        sleva = PercentDiscount(10)
    elif code == "VELKY_NAKUP":
        sleva = BulkDiscount(1000, 5)
    else:
        sleva = NoDiscount()
    kalkulacka = PriceCalculator(sleva)
    return kalkulacka.total(prices)
