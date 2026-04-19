"""Configuration schema validation behavior and value typing."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, List, Optional, Tuple, Union

MISSING_DEFAULT = object()


class ValueType(Enum):
    """Supported configuration value types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    OBJECT = "object"
    PATH = "path"
    REGEX = "regex"


@dataclass
class ValidationRule:
    """Single validation rule for a configuration value."""

    # Type validation
    value_type: ValueType
    required: bool = False

    # Numeric validation
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None

    # String validation
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    allowed_values: Optional[List[str]] = None
    pattern: Optional[str] = None

    # Path validation
    must_exist: bool = False
    must_be_file: bool = False
    must_be_dir: bool = False

    # Custom validation
    custom_validator: Optional[Callable[[Any], bool]] = None
    error_message: Optional[str] = None

    # Default value
    default_value: Any = MISSING_DEFAULT

    def has_default(self) -> bool:
        """Return whether the rule declares an explicit default value."""
        return self.default_value is not MISSING_DEFAULT

    def validate(
        self, value: Any, section: str, key: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a configuration value against this rule.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Type validation
        if not self._validate_type(value):
            return False, self._type_error(section, key, value)

        # Convert value to correct type
        try:
            converted_value = self._convert_value(value)
        except (ValueError, TypeError) as e:
            return False, f"Cannot convert {key} to {self.value_type.value}: {e}"

        # Range validation (only for INTEGER and FLOAT types)
        if self.value_type in [
            ValueType.INTEGER,
            ValueType.FLOAT,
        ] and not self._validate_range(converted_value):
            return False, self._range_error(section, key, converted_value)

        # Length validation (only for STRING and LIST types)
        if self.value_type in [
            ValueType.STRING,
            ValueType.LIST,
        ] and not self._validate_length(converted_value):
            return False, self._length_error(section, key, converted_value)

        # Allowed values validation
        if not self._validate_allowed_values(converted_value):
            return False, self._allowed_values_error(section, key, converted_value)

        # Pattern validation (only for STRING and REGEX types)
        if self.value_type in [
            ValueType.STRING,
            ValueType.REGEX,
        ] and not self._validate_pattern(converted_value):
            return False, self._pattern_error(section, key, converted_value)

        # Path validation (only for PATH type)
        if self.value_type == ValueType.PATH and not self._validate_path(
            converted_value
        ):
            return False, self._path_error(section, key, converted_value)

        # Custom validation
        if self.custom_validator and not self.custom_validator(converted_value):
            return False, self._custom_error(section, key, converted_value)

        return True, None

    def _validate_type(self, value: Any) -> bool:
        """Validate basic type of value."""
        if value is None:
            return self.has_default() and self.default_value is None
        if self.value_type == ValueType.STRING:
            return isinstance(value, str)
        elif self.value_type == ValueType.INTEGER:
            return isinstance(value, (int, str)) and str(value).lstrip("-").isdigit()
        elif self.value_type == ValueType.FLOAT:
            return isinstance(value, (int, float, str)) and self._is_float(str(value))
        elif self.value_type == ValueType.BOOLEAN:
            if isinstance(value, bool):
                return True
            if isinstance(value, str):
                return value.lower() in ("true", "false", "yes", "no", "1", "0")
            return False
        elif self.value_type == ValueType.LIST:
            return isinstance(value, (list, str))
        elif self.value_type == ValueType.OBJECT:
            return isinstance(value, dict)
        elif self.value_type == ValueType.PATH:
            return isinstance(value, str)
        elif self.value_type == ValueType.REGEX:
            return isinstance(value, str)

    def _convert_value(self, value: Any) -> Any:
        """Convert value to correct type."""
        if value is None:
            return None
        if self.value_type == ValueType.INTEGER:
            return int(value)
        elif self.value_type == ValueType.FLOAT:
            return float(value)
        elif self.value_type == ValueType.BOOLEAN:
            if isinstance(value, bool):
                return value
            return value.lower() in ("true", "yes", "1")
        elif self.value_type == ValueType.LIST:
            if isinstance(value, str):
                return [item.strip() for item in value.split(",") if item.strip()]
            return value
        elif self.value_type == ValueType.OBJECT:
            return value
        return value

    def _validate_range(self, value: Any) -> bool:
        """Validate numeric ranges."""
        if self.min_value is not None and value < self.min_value:
            return False
        if self.max_value is not None and value > self.max_value:
            return False
        return True

    def _validate_length(self, value: Any) -> bool:
        """Validate string/list length."""
        if self.min_length is not None and len(value) < self.min_length:
            return False
        if self.max_length is not None and len(value) > self.max_length:
            return False
        return True

    def _validate_allowed_values(self, value: Any) -> bool:
        """Validate against allowed values."""
        if self.allowed_values is None:
            return True

        # For LIST types, check if all items are in allowed values
        if self.value_type == ValueType.LIST:
            if isinstance(value, list):
                return all(item in self.allowed_values for item in value)
            else:
                # value is still a string, convert to list first
                converted_value = self._convert_value(value)
                return all(item in self.allowed_values for item in converted_value)

        return value in self.allowed_values

    def _validate_pattern(self, value: Any) -> bool:
        """Validate against regex pattern."""
        if self.pattern is None:
            return True
        return re.match(self.pattern, str(value)) is not None

    def _validate_path(self, value: Any) -> bool:
        """Validate path-specific requirements."""
        if not isinstance(value, str):
            return False

        if self.must_exist and not os.path.exists(value):
            return False

        if self.must_be_file and not os.path.isfile(value):
            return False

        if self.must_be_dir and not os.path.isdir(value):
            return False

        return True

    def _is_float(self, value: str) -> bool:
        """Check if string can be converted to float."""
        try:
            float(value)
            return True
        except ValueError:
            return False

    # Error message methods
    def _type_error(self, section: str, key: str, value: Any) -> str:
        return (
            f"{section}.{key}: Expected {self.value_type.value}, "
            f"got {type(value).__name__}"
        )

    def _range_error(self, section: str, key: str, value: Any) -> str:
        if self.min_value is not None and self.max_value is not None:
            return (
                f"{section}.{key}: Value {value} not in range "
                f"[{self.min_value}, {self.max_value}]"
            )
        elif self.min_value is not None:
            return (
                f"{section}.{key}: Value {value} is less than minimum {self.min_value}"
            )
        else:
            return f"{section}.{key}: Value {value} is greater than maximum {self.max_value}"

    def _length_error(self, section: str, key: str, value: Any) -> str:
        if self.min_length is not None and self.max_length is not None:
            return (
                f"{section}.{key}: Length {len(value)} not in range "
                f"[{self.min_length}, {self.max_length}]"
            )
        elif self.min_length is not None:
            return f"{section}.{key}: Length {len(value)} is less than minimum {self.min_length}"
        else:
            return f"{section}.{key}: Length {len(value)} is greater than maximum {self.max_length}"

    def _allowed_values_error(self, section: str, key: str, value: Any) -> str:
        return f"{section}.{key}: Value '{value}' not in allowed values: {self.allowed_values}"

    def _pattern_error(self, section: str, key: str, value: Any) -> str:
        return (
            f"{section}.{key}: Value '{value}' does not match pattern '{self.pattern}'"
        )

    def _path_error(self, section: str, key: str, value: Any) -> str:
        if self.must_exist:
            return f"{section}.{key}: Path '{value}' does not exist"
        elif self.must_be_file:
            return f"{section}.{key}: Path '{value}' is not a file"
        elif self.must_be_dir:
            return f"{section}.{key}: Path '{value}' is not a directory"
        return f"{section}.{key}: Invalid path '{value}'"

    def _custom_error(self, section: str, key: str, value: Any) -> str:
        return (
            self.error_message
            or f"{section}.{key}: Custom validation failed for value '{value}'"
        )


__all__ = ["ValueType", "ValidationRule"]
