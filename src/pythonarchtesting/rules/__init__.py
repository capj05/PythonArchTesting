"""
Rules module - supported annotation marker import surface.

This package intentionally exposes only the declaration markers used in
``__archtest__: Annotated[...]`` metadata. Runtime models and declaration
helpers live in their canonical modules.
"""

from __future__ import annotations

from typing import Any, Callable


class _LazyMarkerFactory:
    """Lazy marker-factory proxy to avoid import overhead during CLI startup."""

    def __init__(self, name: str, getter_func: Callable[[], dict[str, Any]]) -> None:
        self._name = name
        self._getter_func = getter_func
        self._cached: Any | None = None

    def _resolve(self) -> Any:
        if self._cached is None:
            self._cached = self._getter_func()[self._name]
        return self._cached

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._resolve()(*args, **kwargs)

    def __repr__(self) -> str:
        return f"<LazyMarkerFactory {self._name}>"


def _get_core_decorators() -> dict[str, Any]:
    from pythonarchtesting.rules.declaration.core import (
        enforce_flow,
        flow,
        forbid_imports,
        implements_protocol,
        required_entity_signature,
        required_method,
    )

    return {
        "required_entity_signature": required_entity_signature,
        "required_method": required_method,
        "forbid_imports": forbid_imports,
        "implements_protocol": implements_protocol,
        "flow": flow,
        "enforce_flow": enforce_flow,
    }


required_entity_signature = _LazyMarkerFactory(
    "required_entity_signature", _get_core_decorators
)
required_method = _LazyMarkerFactory("required_method", _get_core_decorators)
forbid_imports = _LazyMarkerFactory("forbid_imports", _get_core_decorators)
implements_protocol = _LazyMarkerFactory("implements_protocol", _get_core_decorators)
flow = _LazyMarkerFactory("flow", _get_core_decorators)
enforce_flow = _LazyMarkerFactory("enforce_flow", _get_core_decorators)

__all__ = [
    "required_entity_signature",
    "required_method",
    "forbid_imports",
    "implements_protocol",
    "flow",
    "enforce_flow",
]
