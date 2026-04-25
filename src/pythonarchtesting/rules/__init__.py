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
        does_not_have,
        enforce_flow,
        exact_type,
        flow,
        forbid_imports,
        implements_protocol,
        inherits_directly_from,
        is_enum,
        not_subclass_of,
        required_attribute,
        required_constructor,
        required_entity_signature,
        required_factory,
        required_method,
        subclass_of,
    )

    return {
        "required_entity_signature": required_entity_signature,
        "required_method": required_method,
        "required_factory": required_factory,
        "required_constructor": required_constructor,
        "required_attribute": required_attribute,
        "does_not_have": does_not_have,
        "forbid_imports": forbid_imports,
        "implements_protocol": implements_protocol,
        "subclass_of": subclass_of,
        "exact_type": exact_type,
        "not_subclass_of": not_subclass_of,
        "inherits_directly_from": inherits_directly_from,
        "is_enum": is_enum,
        "flow": flow,
        "enforce_flow": enforce_flow,
    }


required_entity_signature = _LazyMarkerFactory(
    "required_entity_signature", _get_core_decorators
)
required_method = _LazyMarkerFactory("required_method", _get_core_decorators)
required_factory = _LazyMarkerFactory("required_factory", _get_core_decorators)
required_constructor = _LazyMarkerFactory("required_constructor", _get_core_decorators)
required_attribute = _LazyMarkerFactory("required_attribute", _get_core_decorators)
does_not_have = _LazyMarkerFactory("does_not_have", _get_core_decorators)
forbid_imports = _LazyMarkerFactory("forbid_imports", _get_core_decorators)
implements_protocol = _LazyMarkerFactory("implements_protocol", _get_core_decorators)
subclass_of = _LazyMarkerFactory("subclass_of", _get_core_decorators)
exact_type = _LazyMarkerFactory("exact_type", _get_core_decorators)
not_subclass_of = _LazyMarkerFactory("not_subclass_of", _get_core_decorators)
inherits_directly_from = _LazyMarkerFactory(
    "inherits_directly_from", _get_core_decorators
)
is_enum = _LazyMarkerFactory("is_enum", _get_core_decorators)
flow = _LazyMarkerFactory("flow", _get_core_decorators)
enforce_flow = _LazyMarkerFactory("enforce_flow", _get_core_decorators)

__all__ = [
    "required_entity_signature",
    "required_method",
    "required_factory",
    "required_constructor",
    "required_attribute",
    "does_not_have",
    "forbid_imports",
    "implements_protocol",
    "subclass_of",
    "exact_type",
    "not_subclass_of",
    "inherits_directly_from",
    "is_enum",
    "flow",
    "enforce_flow",
]
