from __future__ import annotations

from .discounts import Discount


class PriceCalculator:
    def __init__(self, discount: Discount) -> None:
        self.discount = discount

    def total(self, prices: list[float]) -> float:
        # nejdřív kontrola vstupu
        for cena in prices:
            if cena < 0:
                raise ValueError('cena nesmí být záporná')

        soucet = 0.0
        for cena in prices:
            soucet += cena
        vysledek = self.discount.apply(soucet)
        return round(vysledek, 2)
