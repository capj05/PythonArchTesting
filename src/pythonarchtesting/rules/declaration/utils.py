"""
Core descriptor types and utilities for rule declarations.

This module contains immutable descriptor types that annotation markers use to
capture rule intent without performing any runtime operations during import
time.

The active annotation pipeline reads AST metadata from reference source files.
The object-attachment helpers in this module are retained only as a
compatibility surface for older or out-of-repo callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuleSeverity(Enum):
    """Severity levels for rule violations."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Enum):
            return bool(self.value == other.value)
        if isinstance(other, str):
            return bool(self.value == other)
        return False

    def __hash__(self) -> int:
        return hash(self.value)


@dataclass(frozen=True, slots=True)
class RuleSpec:
    """
    Immutable specification for an architecture rule.

    This descriptor captures rule intent without performing any validation
    or runtime operations during declaration time.

    Compatibility note: the active annotation-first runtime does not consume
    attached ``RuleSpec`` objects during compilation.
    """

    kind: str
    message: str | None = None
    severity: RuleSeverity = RuleSeverity.ERROR
    order: int = 0
    tags: set[str] = field(default_factory=set)
    params: dict[str, Any] = field(default_factory=dict)

    def with_order(self, order: int) -> RuleSpec:
        """Create a copy with the specified order."""
        return RuleSpec(
            kind=self.kind,
            message=self.message,
            severity=self.severity,
            order=order,
            tags=self.tags.copy(),
            params=self.params.copy(),
        )


@dataclass(frozen=True, slots=True)
class RuleMarker:
    """
    Passive declaration marker for annotation metadata.

    In the supported pipeline these markers are embedded in
    ``__archtest__: Annotated[...]`` metadata and later extracted from AST.
    """

    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    message: str | None = None
    severity: RuleSeverity = RuleSeverity.ERROR

    def to_spec(self, order: int = 0) -> RuleSpec:
        """Convert this marker into a concrete ``RuleSpec``."""
        params = dict(self.params)
        message = self.message
        if message is None and "message" in params:
            raw_message = params.pop("message")
            message = raw_message if raw_message is None else str(raw_message)
        return RuleSpec(
            kind=self.kind,
            message=message,
            severity=self.severity,
            order=order,
            params=params,
        )


# Attribute name used to store rule specifications on decorated objects
RULE_ATTR = "__archtest_rules__"


def add_rule_spec(obj: Any, spec: RuleSpec) -> None:
    """
    Attach a compatibility ``RuleSpec`` to an object.

    Args:
        obj: The object to decorate (function, class, etc.)
        spec: The rule specification to attach
    """
    rules = getattr(obj, RULE_ATTR, None)
    if rules is None:
        setattr(obj, RULE_ATTR, [spec])
    else:
        # Ensure we're working with a list
        if not isinstance(rules, list):
            rules = list(rules)
        rules.append(spec)
        setattr(obj, RULE_ATTR, rules)


def get_rule_specs(obj: Any) -> list[RuleSpec]:
    """
    Get compatibility ``RuleSpec`` objects attached to an object.

    Args:
        obj: The object to inspect

    Returns:
        List of rule specifications attached to the object
    """
    rules = getattr(obj, RULE_ATTR, [])
    return list(rules) if rules else []


__all__ = [
    "RULE_ATTR",
    "RuleMarker",
    "RuleSeverity",
    "RuleSpec",
    "add_rule_spec",
    "get_rule_specs",
]
