from .shapes import Shape


def total_area(shapes: list[Shape]) -> float:
    total = 0.0
    for shape in shapes:
        total = total + shape.area()
    return total


def describe_all(shapes: list[Shape]) -> str:
    lines = []
    for shape in shapes:
        lines.append(f"{shape.describe()}: plocha {shape.area():.2f}")
    return "\n".join(lines)
