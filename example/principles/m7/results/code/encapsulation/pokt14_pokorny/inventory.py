class Inventory:
    def __init__(self, stock: dict[str, int] | None = None) -> None:
        # vlastni kopie slovniku, aby zmeny zvenku sklad neovlivnily
        self._stock = {}
        if stock is not None:
            for item in stock:
                quantity = stock[item]
                if quantity < 0:
                    raise ValueError("Pocatecni mnozstvi nesmi byt zaporne.")
                if quantity == 0:
                    continue
                self._stock[item] = quantity

    def add(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Pridavat lze jen kladny pocet kusu.")
        self._stock[item] = self._stock.get(item, 0) + quantity

    def remove(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Odebirat lze jen kladny pocet kusu.")
        current = self.quantity(item)
        if current == 0:
            raise ValueError("Polozka " + item + " na sklade neni.")
        if quantity > current:
            raise ValueError("Na sklade neni dost kusu polozky " + item + ".")
        left = current - quantity
        if left == 0:
            del self._stock[item]
        else:
            self._stock[item] = left

    def quantity(self, item: str) -> int:
        return self._stock.get(item, 0)

    def items(self) -> dict[str, int]:
        # kopie, aby upravy vraceneho slovniku sklad nezmenily
        return dict(self._stock)
