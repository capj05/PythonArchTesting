class Inventory:
    def __init__(self, stock: dict[str, int] | None = None) -> None:
        self.data = {}
        if stock is not None:
            for name in stock:
                if stock[name] < 0:
                    raise ValueError("Záporné množství v počáteční zásobě")
            for name in stock:
                if stock[name] > 0:
                    self.data[name] = stock[name]

    def add(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Množství musí být kladné")
        self.data[item] = self.data.get(item, 0) + quantity

    def remove(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Množství musí být kladné")
        if item not in self.data:
            raise ValueError("Položka na skladě není")
        if quantity > self.data[item]:
            raise ValueError("Na skladě není dost kusů")
        self.data[item] = self.data[item] - quantity
        if self.data[item] == 0:
            del self.data[item]

    def quantity(self, item: str) -> int:
        return self.data.get(item, 0)

    def items(self) -> dict[str, int]:
        return dict(self.data)
