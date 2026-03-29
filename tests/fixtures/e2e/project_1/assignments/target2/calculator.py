"""
Calculator Module - Target 2 Implementation
Implementation with some bugs and missing features.
"""


def normalize_operands(a, b):
    """Signature intentionally incompatible with reference optional parameter."""
    return a, b


class Calculator:
    """Calculator class with basic operations."""

    def __init__(self):
        self.history = []

    def add(self, a, b):
        """Add two numbers."""
        return a + b

    def subtract(self, a, b):
        """Subtract two numbers."""
        return a - b

    def multiply(self, a, b):
        """Multiply two numbers."""
        return a * b

    def divide(self, a, b):
        """Divide two numbers."""
        if b == 0:
            return "Error: Division by zero"
        return a / b

    def power(self, a, b):
        """Calculate power - missing implementation."""
        # TODO: Implement this function

    def get_history(self):
        """Get history - not implemented."""
        return []

    def clear_history(self):
        """Clear history - not implemented."""
