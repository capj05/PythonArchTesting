"""Reference module for the API003 / required_attribute + required_constructor showcase."""

from .contracts import (
    CtorAllowInherited,
    HasCompatibleCtor,
    HasDataclassField,
    HasExactCtor,
    HasName,
    HasPropertyOk,
    HasVersion,
)

__all__ = [
    "CtorAllowInherited",
    "HasCompatibleCtor",
    "HasDataclassField",
    "HasExactCtor",
    "HasName",
    "HasPropertyOk",
    "HasVersion",
]
