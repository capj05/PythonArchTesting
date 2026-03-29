"""
Python Architecture Testing toolkit package.
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_SUBMODULES = {
    "state": "src.state",
    "runner_multi": "src.runner_multi",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY_SUBMODULES.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_path)
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_SUBMODULES))


__all__ = sorted(_LAZY_SUBMODULES)
