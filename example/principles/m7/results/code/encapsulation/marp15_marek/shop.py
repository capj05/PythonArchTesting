from .inventory import Inventory


def sell(inventory: Inventory, item: str, quantity: int) -> None:
    inventory.remove(item, quantity)


def restock(inventory: Inventory, deliveries: dict[str, int]) -> None:
    for name, q in deliveries.items():
        if q <= 0:
            raise ValueError("Mnozstvi v dodavce musi byt kladne")
    for name, q in deliveries.items():
        inventory.add(name, q)


def clear_out(inventory: Inventory, item: str) -> int:
    q = inventory.quantity(item)
    if q > 0:
        inventory.remove(item, q)
    return q


def report(inventory: Inventory) -> str:
    items = inventory.items()
    if not items:
        return "(sklad je prázdný)"
    lines = []
    for name in sorted(items):
        lines.append(name + ": " + str(items[name]))
    return "\n".join(lines)
