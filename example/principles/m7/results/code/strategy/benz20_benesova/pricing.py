from .discounts import Discount


class PriceCalculator:
    def __init__(self, discount: Discount) -> None:
        self.discount = discount

    def total(self, prices: list[float]) -> float:
        suma = 0
        for p in prices:
            if p < 0:
                raise ValueError("Cena polozky nesmi byt zaporna.")
            suma = suma + p
        return round(self.discount.apply(suma), 2)
