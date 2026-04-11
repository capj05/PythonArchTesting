"""
Centralized constants for Python Architecture Testing toolkit.
This module provides all immutable values used throughout the application.
"""

from enum import Enum
from typing import Dict, Final

# ============================================================================
# FILE SYSTEM CONSTANTS
# ============================================================================


class FileConstants:
    """File system and path-related constants."""

    # File extensions
    PYTHON_EXTENSION: Final[str] = ".py"
    JSON_EXTENSION: Final[str] = ".json"
    CONFIG_EXTENSION: Final[str] = ".conf"

    # Special file names
    INIT_FILENAME: Final[str] = "__init__.py"

    # Configuration files
    DEFAULT_CONFIG_FILE: Final[str] = "defaults.conf"
    PYTHON_ARCH_TESTING_CONFIG_FILE: Final[str] = "python_arch_testing.conf"
    LEGACY_CUSTOM_CONFIG_FILE: Final[str] = "custom_config.conf"
    CUSTOM_CONFIG_FILE: Final[str] = LEGACY_CUSTOM_CONFIG_FILE

    # Directory patterns to exclude
    EXCLUDED_DIRS: Final[tuple] = (
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        ".pytest_cache",
        ".mypy_cache",
    )


# ============================================================================
# IMPORT CONSTANTS
# ============================================================================


class ImportConstants:
    """Import-related constants."""

    # Limits
    MAX_MODULES_DEFAULT: Final[int] = 100
    MAX_IMPORT_DEPTH: Final[int] = 10

    # Standard library modules (for import ordering)
    STDLIB_MODULES: Final[set] = {
        "sys",
        "os",
        "json",
        "typing",
        "dataclasses",
        "enum",
        "ast",
        "re",
        "textwrap",
        "inspect",
        "fnmatch",
        "pathlib",
        "importlib",
        "time",
        "hashlib",
        "configparser",
    }


# ============================================================================
# REPORTING CONSTANTS
# ============================================================================


class ReportingConstants:
    """Reporting and output formatting constants."""

    # String limits
    MAX_STRING_REPRESENTATION: Final[int] = 100
    MAX_ERROR_MESSAGE_LENGTH: Final[int] = 500
    MAX_DESCRIPTION_LENGTH: Final[int] = 50

    # Output formats
    JSON_FORMAT: Final[str] = "json"
    MARKDOWN_FORMAT: Final[str] = "markdown"
    # Status icons for markdown reports
    STATUS_ICONS: Final[Dict[str, str]] = {
        "OK": "✅",
        "ERROR": "❌",
        "WARNING": "⚠️",
        "FAILED": "❌",
        "NOT_STARTED": "⏳",
        "IN_PROGRESS": "🔄",
        "COMPLETED": "✅",
        "PROCESSING": "🔄",
    }


# ============================================================================
# VALIDATION CONSTANTS
# ============================================================================


class ValidationConstants:
    """Validation-related constants."""

    # Status values
    class ValidationStatus(Enum):
        NOT_STARTED = "not_started"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        FAILED = "failed"
        ERROR = "error"
        WARNING = "warning"
        OK = "ok"
        PROCESSING = "processing"

    # Error codes
    class ErrorCodes:
        CONFIG_FILE_NOT_FOUND = "CONFIG_FILE_NOT_FOUND"
        CONFIG_LOAD_ERROR = "CONFIG_LOAD_ERROR"
        CONFIG_INVALID_BOOLEAN = "CONFIG_INVALID_BOOLEAN"
        CONFIG_INVALID_INTEGER = "CONFIG_INVALID_INTEGER"
        CONFIG_VALIDATION_FAILED = "CONFIG_VALIDATION_FAILED"
        MODULE_IMPORT_FAILED = "MODULE_IMPORT_FAILED"
        CIRCULAR_IMPORT = "CIRCULAR_IMPORT"
        UNEXPECTED_IMPORT_ERROR = "UNEXPECTED_IMPORT_ERROR"
        TYPE_CHECK_ERROR = "TYPE_CHECK_ERROR"
        STRUCTURAL_CHECK_ERROR = "STRUCTURAL_CHECK_ERROR"


# ============================================================================
# PERFORMANCE CONSTANTS
# ============================================================================


class PerformanceConstants:
    """Performance-related constants."""

    # Timeouts and delays
    DEFAULT_TIMEOUT: Final[int] = 30
    CACHE_HIT_RATE_MULTIPLIER: Final[int] = 100

    # Performance thresholds
    MAX_FUNCTION_LENGTH: Final[int] = 50
    MAX_CYCLOMATIC_COMPLEXITY: Final[int] = 10
    MAX_NESTING_DEPTH: Final[int] = 4
    MAX_COGNITIVE_COMPLEXITY: Final[int] = 15


# ============================================================================
# ERROR MESSAGES
# ============================================================================


class ErrorMessages:
    """Standardized error messages."""

    MESSAGES: Final[Dict[str, str]] = {
        "ImportError": "Check if the module path is correct and the module is installed.",
        "AttributeError": "Verify that the attribute exists and is accessible.",
        "TypeError": "Check type annotations and ensure values match expected types.",
        "ValueError": "Check provided values and ensure they are in the correct format.",
        "FileNotFoundError": "Verify that the file path is correct and the file exists.",
        "PermissionError": "Check file permissions and ensure you have necessary access rights.",
    }


# ============================================================================
# STYLE CONSTANTS
# ============================================================================


class StyleConstants:
    """Code style and formatting constants."""

    # Line length
    MAX_LINE_LENGTH: Final[int] = 88  # Black formatter default

    # Import ordering groups
    IMPORT_GROUPS: Final[Dict[str, int]] = {"stdlib": 0, "third-party": 1, "local": 2}

    # Naming patterns
    FUNCTION_NAME_PATTERN: Final[str] = r"^[a-z_][a-z0-9_]*$"
    CLASS_NAME_PATTERN: Final[str] = r"^[A-Z][a-zA-Z0-9]*$"
    CONSTANT_NAME_PATTERN: Final[str] = r"^[A-Z_][A-Z0-9_]*$"


# ============================================================================
# LOGGING CONSTANTS
# ============================================================================


class LoggingConstants:
    """Logging-related constants."""

    # Log levels
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    # Log formats
    DEFAULT_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DETAILED_FORMAT: Final[str] = (
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
