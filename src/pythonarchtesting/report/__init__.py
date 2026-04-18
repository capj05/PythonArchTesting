"""
Report generation submodule for validation results.

This module provides generators for the supported report formats and
the dispatcher-based reporting API surface.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


def create_reporter(*args: Any, **kwargs: Any) -> Any:
    """Lazy wrapper for dispatcher reporter creation."""
    from .dispatcher import create_reporter as _func

    return _func(*args, **kwargs)


def get_available_sinks(*args: Any, **kwargs: Any) -> Any:
    """Lazy wrapper for dispatcher sink discovery."""
    from .dispatcher import get_available_sinks as _func

    return _func(*args, **kwargs)


def is_sink_available(*args: Any, **kwargs: Any) -> Any:
    """Lazy wrapper for dispatcher sink checks."""
    from .dispatcher import is_sink_available as _func

    return _func(*args, **kwargs)


def register_sink(*args: Any, **kwargs: Any) -> Any:
    """Lazy wrapper for dispatcher sink registration."""
    from .dispatcher import register_sink as _func

    return _func(*args, **kwargs)


def __getattr__(name: str) -> Any:
    if name != "BaseReportGenerator":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return import_module("pythonarchtesting.report.base_generator").BaseReportGenerator


__all__ = [
    "BaseReportGenerator",
    "create_reporter",
    "get_available_sinks",
    "is_sink_available",
    "register_sink",
]
