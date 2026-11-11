"""
State management submodule for the project.
Provides modular components for project state management, validation,
and discovery.
"""

from pythonarchtesting.constants import ValidationConstants

from .discovery import ModuleDiscovery
from .validation import ValidationResult, rule_result_to_validation

# Re-export ValidationStatus for backward compatibility
ValidationStatus = ValidationConstants.ValidationStatus

__all__ = [
    "ValidationStatus",
    "ValidationResult",
    "rule_result_to_validation",
    "ModuleDiscovery",
]
