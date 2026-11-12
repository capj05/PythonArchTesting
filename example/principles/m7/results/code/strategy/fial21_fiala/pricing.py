from .discounts import Discount


class PriceCalculator:
    def __init__(self, discount: Discount) -> None:
        self.discount = discount

    def total(self, prices: list[float]) -> float:
        soucet = 0
        for p in prices:
            if p < 0:
                raise ValueError("cena položky nesmí být záporná")
            soucet = soucet + p
        return round(self.discount.apply(soucet), 2)
