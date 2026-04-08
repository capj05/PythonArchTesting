"""
Core data models extracted from rules.py.

This module contains the data models and type definitions that were
previously in rules.py, providing a clean separation of data from behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional, Protocol, Tuple

# Type aliases
Severity = Literal["info", "warning", "error"]
Scope = Literal["module", "class", "function", "method"]
EvidenceType = Literal["static", "runtime", "hybrid"]
EvidenceSource = Literal[
    "ast",
    "filesystem",
    "runtime",
    "config",
    "matcher",
    "compiler",
]
RuleStatus = Literal["OK", "FAILED", "SKIPPED", "ERROR"]


@dataclass(frozen=True)
class RuleSelector:
    """Selector for identifying which entities a rule applies to."""

    source_entity_id: str
    explicit_target: dict[str, Any] | None = None


@dataclass(frozen=True)
class Rule:
    """A rule definition for validation."""

    rule_id: str
    rule_type: str
    name: str
    severity: Severity
    scope: Scope
    evidence_type: EvidenceType
    selector: RuleSelector
    params: Dict[str, Any]
    message_template: str
    fix_hints: Tuple[str, ...] = ()
    enabled: bool = True
    version: str = "v1"


@dataclass(frozen=True)
class Evidence:
    """Evidence collected during rule evaluation."""

    evidence_id: str
    type: str
    source: EvidenceSource
    role: Literal["source", "target"]
    entity_id: str | None
    payload: Dict[str, Any]
    location: Dict[str, Any] | None


@dataclass(frozen=True)
class RuleResult:
    """Result of rule evaluation."""

    rule_id: str
    status: RuleStatus
    source_entity_id: str
    target_entity_id: str | None
    match_status: str
    confidence: float
    message: str
    evidence: Tuple[Evidence, ...]
    details: Dict[str, Any]


@dataclass
class EvalContext:
    """Context for rule evaluation with cached data."""

    source_index: Any  # EntityIndex - avoiding import for now
    target_index: Any  # EntityIndex
    matches: Dict[str, Any]  # Dict[str, MatchResult]
    config: Any  # Config
    source_by_id: Dict[str, Any] = field(default_factory=dict)  # Dict[str, Entity]
    target_by_id: Dict[str, Any] = field(default_factory=dict)  # Dict[str, Entity]
    evidence_store: Dict[Tuple[str, str, str], Evidence] = field(default_factory=dict)
    evidence_stats: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize entity lookup dictionaries."""
        if not self.source_by_id:
            self.source_by_id = {
                entity.canonical_id: entity for entity in self.source_index.all_sorted
            }
        if not self.target_by_id:
            self.target_by_id = {
                entity.canonical_id: entity for entity in self.target_index.all_sorted
            }


class RuleEvaluator(Protocol):
    """Protocol for rule evaluators."""

    def evaluate(
        self,
        rule: Rule,
        source: Any,  # Entity
        target: Any,  # Entity
        match: Any,  # MatchResult
        ctx: EvalContext,
    ) -> RuleResult:
        """Evaluate a rule against entities."""
        ...


@dataclass(frozen=True)
class ArchRule:
    """Architecture-level rule definition."""

    rule_id: str
    kind: str
    scope: Optional[Any]  # EntityKind
    severity: Severity
    source_entity_id: str
    params: Dict[str, Any]
    message_template: str
    fix_hints: Tuple[str, ...]
    evidence_type: EvidenceType
    min_runtime_mode: str = "static-only"
    evidence_types: Tuple[str, ...] = ()
    enabled: bool = True
    activation_source: str | None = None


__all__ = [
    # Type aliases
    "Severity",
    "Scope",
    "EvidenceType",
    "EvidenceSource",
    "RuleStatus",
    # Data models
    "RuleSelector",
    "Rule",
    "Evidence",
    "RuleResult",
    "EvalContext",
    "ArchRule",
    # Protocols
    "RuleEvaluator",
]
