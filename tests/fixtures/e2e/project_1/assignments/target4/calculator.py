"""
Calculator Module - Target 4 Implementation
Alternative approach with different method names and structure.
"""

from typing import List, Union

Number = Union[int, float]


class Calculator:
    """Calculator with enhanced functionality."""

    def __init__(self):
        """Initialize calculator with history tracking."""
        self._history: List[str] = []
        self._operation_count = 0

    def addition(self, a: Number, b: Number) -> Number:
        """Perform addition (different method name)."""
        self._validate_inputs(a, b)
        result = a + b
        self._add_to_history("addition", a, b, result)
        return result

    def subtraction(self, a: Number, b: Number) -> Number:
        """Perform subtraction (different method name)."""
        self._validate_inputs(a, b)
        result = a - b
        self._add_to_history("subtraction", a, b, result)
        return result

    def multiplication(self, a: Number, b: Number) -> Number:
        """Perform multiplication (different method name)."""
        self._validate_inputs(a, b)
        result = a * b
        self._add_to_history("multiplication", a, b, result)
        return result

    def division(self, a: Number, b: Number) -> Number:
        """Perform division (different method name)."""
        self._validate_inputs(a, b)
        if b == 0:
            raise ValueError("Division by zero is not allowed")
        result = a / b
        self._add_to_history("division", a, b, result)
        return result

    def exponentiation(self, a: Number, b: Number) -> Number:
        """Perform exponentiation (different method name)."""
        self._validate_inputs(a, b)
        result = a**b
        self._add_to_history("exponentiation", a, b, result)
        return result

    def _validate_inputs(self, a: Number, b: Number) -> None:
        """Validate input parameters."""
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            raise TypeError("Both inputs must be numbers")

    def _add_to_history(
        self, operation: str, a: Number, b: Number, result: Number
    ) -> None:
        """Add operation to history."""
        self._operation_count += 1
        self._history.append(
            f"Op #{self._operation_count}: {operation}({a}, {b}) = {result}"
        )

    def get_calculation_history(self) -> List[str]:
        """Get calculation history (different method name)."""
        return self._history.copy()

    def reset_history(self) -> None:
        """Reset history (different method name)."""
        self._history.clear()
        self._operation_count = 0

    def get_operation_count(self) -> int:
        """Get total operation count (extra method)."""
        return self._operation_count
