from __future__ import annotations

import math
from abc import ABC, abstractmethod


class Shape(ABC):
    @abstractmethod
    def area(self) -> float:
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> str:
        raise NotImplementedError


class Circle(Shape):
    def __init__(self, radius: float) -> None:
        if radius <= 0:
            raise ValueError("poloměr musí být kladný")
        self.radius = radius

    def area(self) -> float:
        return math.pi * self.radius**2

    def describe(self) -> str:
        return f"kruh o poloměru {self.radius}"


class Rectangle(Shape):
    def __init__(self, width: float, height: float) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("strany musí být kladné")
        self.width = width
        self.height = height

    def area(self) -> float:
        return self.width * self.height

    def describe(self) -> str:
        return f"obdélník {self.width} x {self.height}"


class Square:
    def __init__(self, side: float) -> None:
        if side <= 0:
            raise ValueError("strana musí být kladná")
        self.side = side

    def area(self) -> float:
        return self.side**2

    def describe(self) -> str:
        return f"čtverec o straně {self.side}"
