class Inventory:
    def __init__(self, stock: dict[str, int] | None = None) -> None:
        self._stock = {}
        if stock is not None:
            for name, q in stock.items():
                if q < 0:
                    raise ValueError("Záporné množství v počáteční zásobě")
            for name, q in stock.items():
                if q > 0:
                    self._stock[name] = q

    def add(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Množství musí být kladné")
        self._stock[item] = self._stock.get(item, 0) + quantity

    def remove(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Množství musí být kladné")
        have = self._stock.get(item, 0)
        if quantity > have:
            raise ValueError("Na skladě není dost kusů")
        if quantity == have:
            del self._stock[item]
        else:
            self._stock[item] = have - quantity

    def quantity(self, item: str) -> int:
        return self._stock.get(item, 0)

    def items(self) -> dict[str, int]:
        return dict(self._stock)
