"""
Error utilities for the Python Architecture Testing toolkit.

This module provides utilities for building contextual error messages,
collecting error context, and providing helpful suggestions.
"""

import inspect
from typing import Any, Optional

from src.exceptions import ArchitectureTestingError, ErrorContext


class ErrorMessageBuilder:
    """Builds contextual error messages."""

    @staticmethod
    def get_caller_context(skip_frames: int = 1) -> ErrorContext:
        """Get context from call stack."""
        frame = inspect.currentframe()
        try:
            for _ in range(skip_frames + 1):
                if frame is None:
                    break
                frame = frame.f_back

            if frame is None:
                return ErrorContext()

            return ErrorContext(
                file=frame.f_code.co_filename,
                line=frame.f_lineno,
                function=frame.f_code.co_name,
                module=frame.f_globals.get("__name__"),
            )
        finally:
            del frame

    @staticmethod
    def build_type_error_message(
        param_name: str,
        expected_type: Any,
        actual_type: Any,
        value: Any,
        context: Optional[ErrorContext] = None,
    ) -> str:
        """Build detailed type error message."""
        message = (
            f"Type mismatch for parameter '{param_name}': "
            f"expected {expected_type}, got {actual_type}"
        )

        # Add value hint if it's a simple type
        if isinstance(value, (int, str, bool, float)):
            message += f" (value: {repr(value)})"

        return message

    @staticmethod
    def get_suggestion_for_error(error: Exception) -> Optional[str]:
        """Get helpful suggestion for common errors."""
        suggestions = {
            "ImportError": "Check if the module path is correct and the module is installed.",
            "AttributeError": "Verify that the attribute exists and is accessible.",
            "TypeError": "Check type annotations and ensure values match expected types.",
            "ConfigurationError": "Verify configuration file syntax and values.",
            "ValueError": "Check if the provided value is in the correct format.",
            "FileNotFoundError": "Verify the file path and ensure the file exists.",
            "PermissionError": "Check file/directory permissions.",
        }

        error_type = type(error).__name__
        return suggestions.get(error_type)

    @staticmethod
    def create_error_with_context(
        message: str,
        exception_type: type = ArchitectureTestingError,
        error_code: Optional[str] = None,
        original_error: Optional[Exception] = None,
        skip_frames: int = 2,
    ) -> ArchitectureTestingError:
        """Create an error with automatic context collection."""
        context = ErrorMessageBuilder.get_caller_context(skip_frames)
        suggestion = None

        if original_error:
            suggestion = ErrorMessageBuilder.get_suggestion_for_error(original_error)

        return exception_type(  # type: ignore
            message=message,
            context=context,
            error_code=error_code,
            suggestion=suggestion,
            original_error=original_error,
        )
