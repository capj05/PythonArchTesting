from .discounts import Discount


class PriceCalculator:
    def __init__(self, discount: Discount) -> None:
        self.discount = discount

    def total(self, prices: list[float]) -> float:
        for price in prices:
            if price < 0:
                raise ValueError("cena položky nesmí být záporná")
        subtotal = sum(prices, 0.0)
        discounted = self.discount.apply(subtotal)
        return round(discounted, 2)
