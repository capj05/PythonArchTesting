class Inventory:
    def __init__(self, stock: dict[str, int] | None = None) -> None:
        self.stock = {}
        if stock is not None:
            for item in stock:
                if stock[item] < 0:
                    raise ValueError("Množství nesmí být záporné")
            for item in stock:
                if stock[item] > 0:
                    self.stock[item] = stock[item]

    def add(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Množství musí být kladné")
        if item in self.stock:
            self.stock[item] = self.stock[item] + quantity
        else:
            self.stock[item] = quantity

    def remove(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Množství musí být kladné")
        if item not in self.stock:
            raise ValueError("Položka není na skladě")
        if self.stock[item] < quantity:
            raise ValueError("Na skladě není dost kusů")
        self.stock[item] = self.stock[item] - quantity
        if self.stock[item] == 0:
            del self.stock[item]

    def quantity(self, item: str) -> int:
        if item in self.stock:
            return self.stock[item]
        return 0

    def items(self) -> dict[str, int]:
        return dict(self.stock)
