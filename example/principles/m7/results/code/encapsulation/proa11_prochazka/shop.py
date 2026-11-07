from .inventory import Inventory


def sell(inventory: Inventory, item: str, quantity: int) -> None:
    inventory.remove(item, quantity)


def restock(inventory: Inventory, deliveries: dict[str, int]) -> None:
    # nejdriv kontrola cele dodavky, pak teprve naskladneni
    for item, quantity in deliveries.items():
        if quantity <= 0:
            raise ValueError("v dodavce je nekladne mnozstvi u polozky " + item)
    for item, quantity in deliveries.items():
        inventory.add(item, quantity)


def clear_out(inventory: Inventory, item: str) -> int:
    count = inventory.quantity(item)
    if count > 0:
        inventory.remove(item, count)
    return count


def report(inventory: Inventory) -> str:
    stock = inventory.items()
    if len(stock) == 0:
        return "(sklad je prazdny)"
    lines = []
    for item in sorted(stock):
        lines.append(item + ": " + str(stock[item]))
    return "\n".join(lines)
