"""
Calculator Module - Source Reference Implementation
This module demonstrates basic arithmetic operations with proper error handling.
"""

import numbers
from typing import Annotated, List, Union

from src.rules import required_entity_signature, required_method

# Type annotations for better type checking
Number = Union[int, float]


def normalize_operands(a: Number, b: Number = 0) -> tuple[Number, Number]:
    """Normalize calculator operands before operations."""
    __archtest__: Annotated[  # noqa: F842
        None,
        required_entity_signature(mode="compatible", return_annotation="warning"),
    ]
    return a, b


class Calculator:
    """
    A simple calculator class that performs basic arithmetic operations.

    Attributes:
        history (List[str]): Stores calculation history
    """

    def __init__(self):
        """Initialize calculator with empty history."""
        self.history: List[str] = []

    def add(self, a: Number, b: Number) -> Number:
        """
        Add two numbers together.

        Args:
            a: First number
            b: Second number

        Returns:
            Sum of a and b

        Raises:
            TypeError: If either argument is not a number
        """
        __archtest__: Annotated[  # noqa: F842
            None,
            required_method(signature_mode="compatible"),
        ]
        if not isinstance(a, numbers.Number) or not isinstance(b, numbers.Number):
            raise TypeError("Both arguments must be numbers")

        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result

    def subtract(self, a: Number, b: Number) -> Number:
        """
        Subtract second number from first number.

        Args:
            a: First number (minuend)
            b: Second number (subtrahend)

        Returns:
            Difference of a and b

        Raises:
            TypeError: If either argument is not a number
        """
        if not isinstance(a, numbers.Number) or not isinstance(b, numbers.Number):
            raise TypeError("Both arguments must be numbers")

        result = a - b
        self.history.append(f"{a} - {b} = {result}")
        return result

    def multiply(self, a: Number, b: Number) -> Number:
        """
        Multiply two numbers.

        Args:
            a: First number
            b: Second number

        Returns:
            Product of a and b

        Raises:
            TypeError: If either argument is not a number
        """
        if not isinstance(a, numbers.Number) or not isinstance(b, numbers.Number):
            raise TypeError("Both arguments must be numbers")

        result = a * b
        self.history.append(f"{a} * {b} = {result}")
        return result

    def divide(self, a: Number, b: Number) -> Number:
        """
        Divide first number by second number.

        Args:
            a: First number (dividend)
            b: Second number (divisor)

        Returns:
            Quotient of a and b

        Raises:
            TypeError: If either argument is not a number
            ZeroDivisionError: If divisor is zero
        """
        if not isinstance(a, numbers.Number) or not isinstance(b, numbers.Number):
            raise TypeError("Both arguments must be numbers")

        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero")

        result = a / b
        self.history.append(f"{a} / {b} = {result}")
        return result

    def power(self, a: Number, b: Number) -> Number:
        """
        Raise first number to the power of second number.

        Args:
            a: Base number
            b: Exponent number

        Returns:
            a raised to the power of b

        Raises:
            TypeError: If either argument is not a number
        """
        __archtest__: Annotated[  # noqa: F842
            None,
            required_method(signature_mode="compatible"),
        ]
        if not isinstance(a, numbers.Number) or not isinstance(b, numbers.Number):
            raise TypeError("Both arguments must be numbers")

        result = a**b
        self.history.append(f"{a} ^ {b} = {result}")
        return result

    def get_history(self) -> List[str]:
        """
        Get calculation history.

        Returns:
            List of calculation history strings
        """
        return self.history.copy()

    def clear_history(self) -> None:
        """Clear calculation history."""
        self.history.clear()
