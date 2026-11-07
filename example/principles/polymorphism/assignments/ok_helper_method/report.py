from __future__ import annotations

from .shapes import Shape


def total_area(shapes: list[Shape]) -> float:
    total = 0.0
    for shape in shapes:
        total += shape.area()
    return total


def describe_all(shapes: list[Shape]) -> str:
    lines = [f"{shape.describe()}: plocha {shape.area():.2f}" for shape in shapes]
    return "\n".join(lines)
