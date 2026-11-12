from .discounts import Discount


class PriceCalculator:
    def __init__(self, discount: Discount) -> None:
        self.discount = discount

    def total(self, prices: list[float]) -> float:
        for price in prices:
            if price < 0:
                raise ValueError("Cena položky nesmí být záporná.")
        total = 0.0
        for price in prices:
            total = total + price
        total = self.discount.apply(total)
        return round(total, 2)
