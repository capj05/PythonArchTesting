"""Typed intermediate representation for reporting."""

from .builder import build_multi_target_report_ir
from .models import (
    AggregateSummary,
    EntityRef,
    EvidenceItem,
    MatchingSection,
    MatchingSummary,
    ReportDocument,
    ResultItem,
    ResultsSummary,
    RunMeta,
    TargetReport,
)
from .serialize import to_legacy_schema_v2

__all__ = [
    "AggregateSummary",
    "EntityRef",
    "EvidenceItem",
    "MatchingSection",
    "MatchingSummary",
    "ReportDocument",
    "ResultItem",
    "ResultsSummary",
    "RunMeta",
    "TargetReport",
    "build_multi_target_report_ir",
    "to_legacy_schema_v2",
]
