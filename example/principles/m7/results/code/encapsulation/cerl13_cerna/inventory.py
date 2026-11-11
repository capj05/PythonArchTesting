class Inventory:
    def __init__(self, stock: dict[str, int] | None = None) -> None:
        # own copy of the stock, so changes to the given dict do not reach the inventory
        self._stock = {}
        if stock is not None:
            for item in stock:
                count = stock[item]
                if count < 0:
                    raise ValueError("počáteční množství nesmí být záporné")
                if count > 0:
                    self._stock[item] = count

    def add(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("přidávat lze jen kladný počet kusů")
        self._stock[item] = self._stock.get(item, 0) + quantity

    def remove(self, item: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("ubírat lze jen kladný počet kusů")
        current = self._stock.get(item, 0)
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
