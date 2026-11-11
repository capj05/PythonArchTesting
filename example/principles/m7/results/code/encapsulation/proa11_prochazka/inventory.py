class Inventory:
    def __init__(self, stock: dict[str, int] | None = None) -> None:
        # vlastni slovnik, aby zmeny puvodniho slovniku sklad neovlivnily
        self._stock = {}
        if stock is not None:
            for item, quantity in stock.items():
                if quantity < 0:
                    raise ValueError("pocatecni mnozstvi nesmi byt zaporne")
                if quantity > 0:
                    self._stock[item] = quantity

    def add(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("pridavat lze jen kladny pocet kusu")
        self._stock[item] = self._stock.get(item, 0) + quantity

    def remove(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("ubirat lze jen kladny pocet kusu")
        current = self._stock.get(item, 0)
        if current == 0:
            raise ValueError("polozka " + item + " na sklade neni")
        if quantity > current:
            raise ValueError("na sklade neni dost kusu polozky " + item)
        left = current - quantity
        if left == 0:
            del self._stock[item]
        else:
            self._stock[item] = left

    def quantity(self, item: str) -> int:
        return self._stock.get(item, 0)

    def items(self) -> dict[str, int]:
        # kopie, aby upravou vraceneho slovniku nesel sklad zmenit
        return dict(self._stock)
