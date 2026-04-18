"""
State management submodule for the project.
Provides modular components for project state management, validation,
discovery, and memory management.
"""

from pythonarchtesting.constants import ValidationConstants

from .discovery import ModuleDiscovery
from .memory_manager import MemoryManager
from .validation import ValidationResult, rule_result_to_validation

# Re-export ValidationStatus for backward compatibility
ValidationStatus = ValidationConstants.ValidationStatus

__all__ = [
    "ValidationStatus",
    "ValidationResult",
    "rule_result_to_validation",
    "MemoryManager",
    "ModuleDiscovery",
]
