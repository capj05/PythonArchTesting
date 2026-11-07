from __future__ import annotations

from .shapes import Circle, Rectangle, Shape


def total_area(shapes: list[Shape]) -> float:
    total = 0.0
    for shape in shapes:
        total += shape.area()
    return total


def describe_all(shapes: list[Shape]) -> str:
    lines = []
    for shape in shapes:
        if type(shape) == Circle:
            text = f"kruh o poloměru {shape.radius}"
        elif type(shape) == Rectangle:
            text = f"obdélník {shape.width} x {shape.height}"
        else:
            text = f"čtverec o straně {shape.side}"
        lines.append(f"{text}: plocha {shape.area():.2f}")
    return "\n".join(lines)
