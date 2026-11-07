from __future__ import annotations

import math

from .shapes import Circle, Rectangle, Shape, Square


def total_area(shapes: list[Shape]) -> float:
    total = 0.0
    for shape in shapes:
        if isinstance(shape, Circle):
            total += math.pi * shape.radius**2
        elif isinstance(shape, Rectangle):
            total += shape.width * shape.height
        elif isinstance(shape, Square):
            total += shape.side**2
    return total


def describe_all(shapes: list[Shape]) -> str:
    lines = [f"{shape.describe()}: plocha {shape.area():.2f}" for shape in shapes]
    return "\n".join(lines)
