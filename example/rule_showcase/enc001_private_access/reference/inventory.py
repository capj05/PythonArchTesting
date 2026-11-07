"""The inventory keeps its stock private."""


class Inventory:
    def __init__(self, stock: dict[str, int]) -> None:
        self._stock = dict(stock)

    def items(self) -> dict[str, int]:
        return dict(self._stock)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Inventory) and self._stock == other._stock
