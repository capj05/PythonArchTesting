"""
Lazy loading interface for report generation functions.

This module provides lazy access to heavy report generation functions,
ensuring they are only imported when actually needed.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any, List, Optional, cast


def _get_report_module() -> ModuleType:
    """Lazy import of the heavy report module."""
    return import_module("pythonarchtesting.report.api")


def generate_multi_target_report(
    run_state: Any,
    target_states: List[Any],
    output_format: str = "json",
    config: Optional[Any] = None,
    output_path: Optional[str | Path] = None,
) -> str:
    """Lazy wrapper for generate_multi_target_report function."""
    module = _get_report_module()
    return cast(
        str,
        module.generate_multi_target_report(
            run_state, target_states, output_format, config, output_path
        ),
    )


def get_multi_exit_code(
    run_state: Any, target_states: List[Any], config: Optional[Any] = None
) -> int:
    """Lazy wrapper for get_multi_exit_code function."""
    module = _get_report_module()
    return cast(int, module.get_multi_exit_code(run_state, target_states, config))
