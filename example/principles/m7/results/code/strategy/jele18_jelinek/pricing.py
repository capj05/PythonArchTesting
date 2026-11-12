from .discounts import Discount


class PriceCalculator:
    def __init__(self, discount: Discount) -> None:
        self.discount = discount

    def total(self, prices: list[float]) -> float:
        for p in prices:
            if p < 0:
                raise ValueError("Cena položky nesmí být záporná.")
        s = sum(prices)
        return round(self.discount.apply(s), 2)
