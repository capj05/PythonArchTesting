"""
State management submodule for the project.
Provides modular components for project state management, validation,
discovery, and memory management.
"""

import sys

from src.constants import ValidationConstants

from .discovery import ModuleDiscovery
from .memory_manager import MemoryManager
from .project_state import ProjectState
from .validation import ValidationResult, rule_result_to_validation

# Re-export ValidationStatus for backward compatibility
ValidationStatus = ValidationConstants.ValidationStatus

__all__ = [
    "ValidationStatus",
    "ValidationResult",
    "rule_result_to_validation",
    "MemoryManager",
    "ModuleDiscovery",
    "ProjectState",
]

# Backward compatibility for dotted monkeypatch paths like "src.state.state.*".
state = sys.modules[__name__]
