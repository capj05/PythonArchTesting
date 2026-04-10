"""Compatibility single-target state layer built on older runtime assumptions."""

from __future__ import annotations

from pythonarchtesting.constants import ValidationConstants

from ._core import ProjectState

ValidationStatus = ValidationConstants.ValidationStatus

__all__ = [
    "ValidationStatus",
    "ProjectState",
]
