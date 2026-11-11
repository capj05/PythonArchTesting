from __future__ import annotations


class Inventory:
    def __init__(self, stock: dict[str, int] | None = None) -> None:
        self._stock: dict[str, int] = dict(stock or {})
        self.log: list[str] = []

    def add(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("množství musí být kladné")
        self._stock[item] = self._stock.get(item, 0) + quantity
        self.log.append(f"+{quantity} {item}")

    def remove(self, item: str, quantity: int) -> None:
        if quantity > self.quantity(item):
            raise ValueError(f"na skladě není dost: {item}")
        self._stock[item] -= quantity
        if self._stock[item] == 0:
            del self._stock[item]
        self.log.append(f"-{quantity} {item}")

    def quantity(self, item: str) -> int:
        return self._stock.get(item, 0)

    def items(self) -> dict[str, int]:
        return dict(self._stock)
