from .shapes import Shape


def total_area(shapes: list[Shape]) -> float:
    total = 0.0
    for s in shapes:
        total += s.area()
    return total


def describe_all(shapes: list[Shape]) -> str:
    lines = []
    for s in shapes:
        lines.append(f"{s.describe()}: plocha {s.area():.2f}")
    return "\n".join(lines)
