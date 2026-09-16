"""Reference module for the NEG001 / does_not_have showcase."""

from .prohibitions import (
    DeclaredNoSecret,
    NoConstantsClass,
    NoDangerousAliases,
    NoDebugMethods,
    NoSecret,
)

__all__ = [
    "DeclaredNoSecret",
    "NoConstantsClass",
    "NoDangerousAliases",
    "NoDebugMethods",
    "NoSecret",
]
