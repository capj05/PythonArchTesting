from .inventory import Inventory


def sell(inventory: Inventory, item: str, quantity: int) -> None:
    inventory.remove(item, quantity)


def restock(inventory: Inventory, deliveries: dict[str, int]) -> None:
    for item in deliveries:
        if deliveries[item] <= 0:
            raise ValueError("dodávka obsahuje nekladné množství")
    for item in deliveries:
        inventory.stock[item] = inventory.stock.get(item, 0) + deliveries[item]


def clear_out(inventory: Inventory, item: str) -> int:
    if item not in inventory.stock:
        return 0
    count = inventory.stock[item]
    del inventory.stock[item]
    return count


def report(inventory: Inventory) -> str:
    if len(inventory.stock) == 0:
        return "(sklad je prázdný)"
    lines = []
    for item in sorted(inventory.stock):
        lines.append(item + ": " + str(inventory.stock[item]))
    return "\n".join(lines)
