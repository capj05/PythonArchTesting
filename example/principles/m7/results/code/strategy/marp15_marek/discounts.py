from typing import Protocol


class Discount(Protocol):
    def apply(self, amount: float) -> float: ...


class NoDiscount:
    def apply(self, amount: float) -> float:
        return amount


class PercentDiscount:
    def __init__(self, percent: float) -> None:
        if percent < 0 or percent > 100:
            raise ValueError("Procento musí být mezi 0 a 100.")
        self.percent = percent

    def apply(self, amount: float) -> float:
        return amount * (100 - self.percent) / 100


class BulkDiscount:
    def __init__(self, threshold: float, percent: float) -> None:
        if threshold < 0:
            raise ValueError("Hranice nesmí být záporná.")
        if percent < 0 or percent > 100:
            raise ValueError("Procento musí být mezi 0 a 100.")
        self.threshold = threshold
        self.percent = percent

    def apply(self, amount: float) -> float:
        if amount >= self.threshold:
            return amount * (100 - self.percent) / 100
        return amount
