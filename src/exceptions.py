"""
Custom exception hierarchy for the Python Architecture Testing toolkit.

This module provides a comprehensive set of exceptions with context information,
error codes, and suggestions to improve error handling and debugging.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ErrorContext:
    """Context information for errors."""

    file: Optional[str] = None
    line: Optional[int] = None
    function: Optional[str] = None
    module: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.details is None:
            self.details = {}


class ArchitectureTestingError(Exception):
    """Base exception for all framework errors."""

    def __init__(
        self,
        message: str,
        context: Optional[ErrorContext] = None,
        error_code: Optional[str] = None,
        suggestion: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or ErrorContext()
        self.error_code = error_code
        self.suggestion = suggestion
        self.original_error = original_error

    def __str__(self) -> str:
        """Format error message with context."""
        parts = [self.message]

        if self.context.function:
            parts.append(f"Function: {self.context.function}")
        if self.context.file:
            file_info = self.context.file
            if self.context.line:
                file_info += f":{self.context.line}"
            parts.append(f"Location: {file_info}")
        if self.context.module:
            parts.append(f"Module: {self.context.module}")
        if self.suggestion:
            parts.append(f"Suggestion: {self.suggestion}")
        if self.error_code:
            parts.append(f"Error Code: {self.error_code}")

        return " | ".join(parts)


class ConfigurationError(ArchitectureTestingError):
    """Raised when configuration errors occur."""


class ImportError(ArchitectureTestingError):
    """Raised when module import fails."""


class TypeCheckError(ArchitectureTestingError):
    """Raised when type checking fails."""


class StructuralCheckError(ArchitectureTestingError):
    """Raised when structural checking fails."""


class ValidationError(ArchitectureTestingError):
    """Raised when validation fails."""


class DiscoveryError(ArchitectureTestingError):
    """Raised when module discovery fails."""


class ReportGenerationError(ArchitectureTestingError):
    """Raised when report generation fails."""
