"""
Calculator Module - Target 3 Implementation
Good implementation but missing type hints and some error handling.
"""


def normalize_operands(a, b=0):
    """Normalize calculator operands."""
    return a, b


class Calculator:
    """
    Calculator class for arithmetic operations.
    """

    def __init__(self):
        """Initialize calculator."""
        self.history = []

    def add(self, a, b):
        """Add two numbers together."""
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            raise TypeError("Arguments must be numbers")
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result

    def subtract(self, a, b):
        """Subtract b from a."""
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            raise TypeError("Arguments must be numbers")
        result = a - b
        self.history.append(f"{a} - {b} = {result}")
        return result

    def multiply(self, a, b):
        """Multiply two numbers."""
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            raise TypeError("Arguments must be numbers")
        result = a * b
        self.history.append(f"{a} * {b} = {result}")
        return result

    def divide(self, a, b):
        """Divide a by b."""
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            raise TypeError("Arguments must be numbers")
        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        result = a / b
        self.history.append(f"{a} / {b} = {result}")
        return result

    def power(self, a, b):
        """Calculate a to the power of b."""
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            raise TypeError("Arguments must be numbers")
        result = a**b
        self.history.append(f"{a} ^ {b} = {result}")
        return result

    def get_history(self):
        """Return calculation history."""
        return self.history.copy()

    def clear_history(self):
        """Clear calculation history."""
        self.history.clear()
