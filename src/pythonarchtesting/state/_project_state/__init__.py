"""
Internal single-target state implementation.
"""

from __future__ import annotations

from pythonarchtesting.constants import ValidationConstants

from ._core import ProjectState

ValidationStatus = ValidationConstants.ValidationStatus

__all__ = [
    "ValidationStatus",
    "ProjectState",
]
