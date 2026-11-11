class Inventory:
    def __init__(self, stock: dict[str, int] | None = None) -> None:
        # kopie slovniku, aby pozdejsi zmeny puvodniho slovniku sklad neovlivnily
        self._stock: dict[str, int] = {}
        if stock is None:
            return
        for item in stock:
            quantity = stock[item]
            if quantity < 0:
                raise ValueError("počáteční množství nesmí být záporné")
            if quantity > 0:
                self._stock[item] = quantity

    def add(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("přidávat lze jen kladný počet kusů")
        self._stock[item] = self._stock.get(item, 0) + quantity

    def remove(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("ubírat lze jen kladný počet kusů")
        current = self.quantity(item)
        if current == 0:
            raise ValueError("položka na skladě není")
        if quantity > current:
            raise ValueError("na skladě není dost kusů")
        left = current - quantity
        if left == 0:
            del self._stock[item]
        else:
            self._stock[item] = left

    def quantity(self, item: str) -> int:
        return self._stock.get(item, 0)

    def items(self) -> dict[str, int]:
        return dict(self._stock)
