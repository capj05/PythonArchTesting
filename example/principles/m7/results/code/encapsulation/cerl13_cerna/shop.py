from .inventory import Inventory


def sell(inventory: Inventory, item: str, quantity: int) -> None:
    inventory.remove(item, quantity)


def restock(inventory: Inventory, deliveries: dict[str, int]) -> None:
    # check the whole delivery first, so a bad item leaves the stock unchanged
    for item in deliveries:
        if deliveries[item] <= 0:
            raise ValueError("v dodávce je množství, které není kladné")
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
    for item in sorted(stock):
        lines.append(item + ": " + str(stock[item]))
    return "\n".join(lines)
