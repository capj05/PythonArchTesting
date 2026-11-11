class Inventory:
    def __init__(self, stock: dict[str, int] | None = None) -> None:
        self._stock = {}
        if stock is not None:
            for item in stock:
                if stock[item] < 0:
                    raise ValueError("Mnozstvi nesmi byt zaporne")
            for item in stock:
                if stock[item] > 0:
                    self._stock[item] = stock[item]

    def add(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Mnozstvi musi byt kladne")
        if item in self._stock:
            self._stock[item] = self._stock[item] + quantity
        else:
            self._stock[item] = quantity

    def remove(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Mnozstvi musi byt kladne")
        if item not in self._stock:
            raise ValueError("Polozka neni na sklade")
        if self._stock[item] < quantity:
            raise ValueError("Na sklade neni dost kusu")
        self._stock[item] = self._stock[item] - quantity
        if self._stock[item] == 0:
            del self._stock[item]

    def quantity(self, item: str) -> int:
        if item in self._stock:
            return self._stock[item]
        return 0

    def items(self) -> dict[str, int]:
        return dict(self._stock)
