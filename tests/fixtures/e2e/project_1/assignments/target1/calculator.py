"""
Calculator Module - Target 1 Implementation
Basic implementation with minimal error handling.
"""

from typing import Union

Number = Union[int, float]


def normalize_operands(a: Number, b: Number = 0) -> tuple[Number, Number]:
    """Normalize calculator operands."""
    return a, b


class Calculator:
    """Simple calculator class."""

    def __init__(self):
        self.history = []

    def add(self, a: Number, b: Number) -> Number:
        """Add two numbers."""
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result

    def subtract(self, a: Number, b: Number) -> Number:
        """Subtract two numbers."""
        result = a - b
        self.history.append(f"{a} - {b} = {result}")
        return result

    def multiply(self, a: Number, b: Number) -> Number:
        """Multiply two numbers."""
        result = a * b
        self.history.append(f"{a} * {b} = {result}")
        return result

    def divide(self, a: Number, b: Number) -> Number:
        """Divide two numbers."""
        result = a / b
        self.history.append(f"{a} / {b} = {result}")
        return result

    def power(self, a: Number, b: Number) -> Number:
        """Calculate power."""
        result = a**b
        self.history.append(f"{a} ^ {b} = {result}")
        return result

    def get_history(self):
        """Get calculation history."""
        return self.history

    def clear_history(self):
        """Clear history."""
        self.history = []
