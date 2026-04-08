"""
Report generation submodule for validation results.

This module provides generators for the supported report formats and
the dispatcher-based reporting API surface.
"""

from typing import Any

from .base_generator import BaseReportGenerator
from .dispatcher import (
    create_reporter,
    get_available_sinks,
    is_sink_available,
    register_sink,
)


# Lazy import for generate_validation_report to avoid heavy import chain
def generate_validation_report(*args: Any, **kwargs: Any) -> str:
    """Lazy wrapper for generate_validation_report function."""
    from .api import generate_validation_report as _func

    return _func(*args, **kwargs)


__all__ = [
    "BaseReportGenerator",
    "generate_validation_report",
    "create_reporter",
    "get_available_sinks",
    "is_sink_available",
    "register_sink",
]
