"""
Reporter dispatcher for lazy loading of report generators.

This module provides a factory function that creates reporters on demand,
ensuring that only the selected generator module is imported.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING, Any, Dict, Optional, Protocol, cast

if TYPE_CHECKING:
    from pythonarchtesting.report.base_generator import BaseReportGenerator


class ReporterFactory(Protocol):
    """Protocol for reporter factory functions."""

    def __call__(self, report_data: Any, **kwargs: Any) -> "BaseReportGenerator":
        """Create a reporter instance."""
        ...


# Mapping of sink names to module paths and factory function names
@dataclass(frozen=True, slots=True)
class SinkSpec:
    """Sink mapping metadata."""

    module_path: str
    class_name: str


_SINK_REGISTRY: Dict[str, SinkSpec] = {
    "json": SinkSpec("pythonarchtesting.report.json_generator", "JSONReportGenerator"),
    "markdown": SinkSpec(
        "pythonarchtesting.report.markdown_generator", "MarkdownReportGenerator"
    ),
}


def register_sink(
    sink: str,
    module_path: str,
    class_name: str,
    *,
    optional_extra: Optional[str] = None,
    aliases: Optional[list[str]] = None,
    overwrite: bool = False,
) -> None:
    """
    Register a sink at runtime.

    Primarily for extensibility in downstream integrations.
    """
    names = [sink] + (aliases or [])
    for name in names:
        if not overwrite and name in _SINK_REGISTRY:
            raise ValueError(f"Sink '{name}' is already registered")
        _SINK_REGISTRY[name] = SinkSpec(
            module_path=module_path,
            class_name=class_name,
        )


def create_reporter(
    sink: str, report_data: Any, **kwargs: Any
) -> "BaseReportGenerator":
    """
    Create a reporter instance for the specified sink.

    This function lazily imports the reporter module only when the sink
    is requested, ensuring that heavy dependencies are not loaded unless
    needed.

    Args:
        sink: The name of the output sink (e.g., "json", "markdown")
        report_data: The report data to pass to the reporter
        **kwargs: Additional keyword arguments to pass to the reporter

    Returns:
        A reporter instance implementing BaseReportGenerator

    Raises:
        ValueError: If the sink is not supported
        ImportError: If the required module cannot be imported
    """
    if sink not in _SINK_REGISTRY:
        available_sinks = ", ".join(sorted(_SINK_REGISTRY.keys()))
        raise ValueError(
            f"Unsupported sink '{sink}'. Available sinks: {available_sinks}"
        )

    spec = _SINK_REGISTRY[sink]
    module_path = spec.module_path
    class_name = spec.class_name

    try:
        module = import_module(module_path)
        reporter_class = getattr(module, class_name)
    except ImportError as e:
        raise ImportError(
            f"Failed to import reporter module '{module_path}': {e}"
        ) from e
    except AttributeError as e:
        raise ImportError(
            f"Reporter class '{class_name}' not found in '{module_path}': {e}"
        ) from e

    return cast("BaseReportGenerator", reporter_class(report_data, **kwargs))


def get_available_sinks() -> list[str]:
    """
    Get a list of all available sink names.

    Returns:
        List of supported sink names
    """
    return list(_SINK_REGISTRY.keys())


def is_sink_available(sink: str) -> bool:
    """
    Check if a sink is available (can be imported).

    Args:
        sink: The sink name to check

    Returns:
        True if the sink can be imported, False otherwise
    """
    if sink not in _SINK_REGISTRY:
        return False

    module_path = _SINK_REGISTRY[sink].module_path

    try:
        import_module(module_path)
        return True
    except ImportError:
        return False
