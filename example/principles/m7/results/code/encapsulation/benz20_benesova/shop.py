from .inventory import Inventory


def sell(inventory: Inventory, item: str, quantity: int) -> None:
    inventory.remove(item, quantity)


def restock(inventory: Inventory, deliveries: dict[str, int]) -> None:
    for item in deliveries:
        if deliveries[item] <= 0:
            raise ValueError("V dodavce je nekladne mnozstvi")
    for item in deliveries:
        inventory.add(item, deliveries[item])


def clear_out(inventory: Inventory, item: str) -> int:
    count = inventory.quantity(item)
    if count > 0:
        inventory.remove(item, count)
    return count


def report(inventory: Inventory) -> str:
    stock = inventory.items()
    if len(stock) == 0:
        return "(sklad je prázdný)"
    lines = []
    for name in sorted(stock):
        lines.append(name + ": " + str(stock[name]))
    return "\n".join(lines)
