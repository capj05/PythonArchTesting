from .inventory import Inventory


def sell(inventory: Inventory, item: str, quantity: int) -> None:
    inventory.remove(item, quantity)


def restock(inventory: Inventory, deliveries: dict[str, int]) -> None:
    for name, q in deliveries.items():
        if q <= 0:
            raise ValueError("Množství v dodávce musí být kladné")
    for name, q in deliveries.items():
        inventory.add(name, q)


def clear_out(inventory: Inventory, item: str) -> int:
    q = inventory.quantity(item)
    if q > 0:
        inventory.remove(item, q)
    return q


def report(inventory: Inventory) -> str:
    data = inventory.items()
    if not data:
        return "(sklad je prázdný)"
    return "\n".join(f"{name}: {data[name]}" for name in sorted(data))
