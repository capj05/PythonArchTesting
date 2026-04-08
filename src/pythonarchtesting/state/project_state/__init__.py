"""
ProjectState legacy single-target state package (staging).

Public surface must remain stable:
- ProjectState
- ValidationStatus alias (back-compat)
"""

from __future__ import annotations

from pythonarchtesting.constants import ValidationConstants

from ._core import ProjectState

ValidationStatus = ValidationConstants.ValidationStatus

__all__ = [
    "ValidationStatus",
    "ProjectState",
]
