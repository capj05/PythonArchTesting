"""Typed report intermediate representation (IR)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Tuple


@dataclass(frozen=True, slots=True)
class EntityRef:
    """Entity location/identity in source or target code."""

    module: Optional[str]
    qualname: Optional[str]
    file: Optional[str]
    line: Optional[int]
    cls: Optional[str]
    function: Optional[str]


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """Structured evidence attached to a result."""

    type: str
    payload: Dict[str, Any]
    location_file: Optional[str]
    location_line: Optional[int]
    evidence_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ResultItem:
    """Canonical rule/check result item."""

    result_id: str
    project_id: str
    rule_id: str
    rule_type: Optional[str]
    category: str
    status: str
    severity: str
    message: str
    source_entity_id: Optional[str]
    target_entity_id: Optional[str]
    match_status: Optional[str]
    confidence: Optional[float]
    source: EntityRef
    target: EntityRef
    evidence: Tuple[EvidenceItem, ...]
    details: Dict[str, Any]
    fix_hints: Tuple[str, ...]
    tags: Tuple[str, ...]
    timing_seconds: Optional[float]
    activation_source: Optional[str]
    stable_key: Tuple[str, str, str, str, str]
    ordering_key: Tuple[Any, ...]
    extras: Dict[str, Any]


@dataclass(frozen=True, slots=True)
class MatchingSummary:
    """Derived summary of matching outcomes."""

    total: int
    matched: int
    low_confidence: int
    ambiguous: int
    unmatched: int


@dataclass(frozen=True, slots=True)
class MatchingSection:
    """Matching records and configuration used to compute them."""

    matches: Tuple[Dict[str, Any], ...]
    matching_config: Dict[str, Any]
    summary: MatchingSummary


@dataclass(frozen=True, slots=True)
class ResultsSummary:
    """Result counters and ranked highlights."""

    results_total: int
    status_counts: Dict[str, int]
    severity_counts: Dict[str, int]
    category_counts: Dict[str, int]
    top_rules: Tuple[Dict[str, Any], ...]
    top_source_files: Tuple[Dict[str, Any], ...]
    timings: Optional[Dict[str, Any]]


@dataclass(frozen=True, slots=True)
class TargetReport:
    """Report section for one target/project."""

    target_id: str
    display_name: str
    source_root: Optional[str]
    target_path: str
    tags: Tuple[str, ...]
    mode: str
    matching: MatchingSection
    results: Tuple[ResultItem, ...]
    summary: ResultsSummary
    artifacts: Tuple[Dict[str, Any], ...]
    exit_code: int


@dataclass(frozen=True, slots=True)
class RunMeta:
    """Run-level metadata shared by single and multi reports."""

    generated_at: str
    target_path: Optional[str]
    source_path: Optional[str]
    reference_modules: Tuple[str, ...]
    config_snapshot: Optional[Dict[str, Dict[str, str]]]
    config_fingerprint: Optional[str]
    tool_version: Optional[str]
    mode: str


@dataclass(frozen=True, slots=True)
class AggregateSummary:
    """Top-level summary for the full report."""

    targets_total: Optional[int]
    targets_failed: Optional[int]
    targets_passed: Optional[int]
    results: ResultsSummary


@dataclass(frozen=True, slots=True)
class ReportDocument:
    """Top-level typed document for report content."""

    schema_version: str
    framework_version: str
    generated_at: str
    run: RunMeta
    targets: Tuple[TargetReport, ...]
    summary: AggregateSummary
    exit_code: int
    kind: Literal["single", "multi"]
