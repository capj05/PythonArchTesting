from .inventory import Inventory


def sell(inventory: Inventory, item: str, quantity: int) -> None:
    inventory.remove(item, quantity)


def restock(inventory: Inventory, deliveries: dict[str, int]) -> None:
    for name in deliveries:
        if deliveries[name] <= 0:
            raise ValueError("Množství v dodávce musí být kladné")
    for name in deliveries:
        inventory.add(name, deliveries[name])


def clear_out(inventory: Inventory, item: str) -> int:
    count = inventory.quantity(item)
    if count > 0:
        inventory.remove(item, count)
    return count


def report(inventory: Inventory) -> str:
    items = inventory.items()
    if len(items) == 0:
        return "(sklad je prázdný)"
    lines = []
    for name in sorted(items):
        lines.append(name + ": " + str(items[name]))
    return "\n".join(lines)
