"""Reference module for the API001 / required_entity_signature showcase."""

from .signatures import (
    compatible_baseline,
    exact_strict,
    flexible_extras,
    must_keep_return,
    rename_allowed,
    rename_forbidden,
    return_ignore,
)

__all__ = [
    "compatible_baseline",
    "exact_strict",
    "flexible_extras",
    "must_keep_return",
    "rename_allowed",
    "rename_forbidden",
    "return_ignore",
]
