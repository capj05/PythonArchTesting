"""Serialize typed IR back to legacy schema-v2 dictionaries."""

from __future__ import annotations

from typing import Any, Dict

from .models import (
    EntityRef,
    EvidenceItem,
    MatchingSection,
    ReportDocument,
    ResultItem,
    TargetReport,
)


def _entity_to_dict(entity: EntityRef) -> Dict[str, Any]:
    return {
        "module": entity.module,
        "qualname": entity.qualname,
        "file": entity.file,
        "line": entity.line,
    }


def _entity_location(entity: EntityRef) -> Dict[str, Any]:
    return {
        "module": entity.module,
        "qualname": entity.qualname,
        "file": entity.file,
        "line": entity.line,
        "class": entity.cls,
        "function": entity.function,
    }


def _evidence_to_dict(item: EvidenceItem) -> Dict[str, Any]:
    location = None
    if item.location_file is not None or item.location_line is not None:
        location = {"file": item.location_file, "line": item.location_line}
    payload = dict(item.payload)
    if item.evidence_id is not None and "evidence_id" not in payload:
        payload["evidence_id"] = item.evidence_id
    return {
        "type": item.type,
        "payload": payload,
        "location": location,
    }


def _result_to_dict(item: ResultItem) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "rule_id": item.rule_id,
        "rule_type": item.rule_type,
        "status": item.status,
        "severity": item.severity,
        "message": item.message,
        "source_entity_id": item.source_entity_id,
        "target_entity_id": item.target_entity_id,
        "match_status": item.match_status,
        "confidence": item.confidence,
        "source": _entity_to_dict(item.source),
        "target": _entity_to_dict(item.target),
        "evidence": [_evidence_to_dict(ev) for ev in item.evidence],
        "details": dict(item.details),
        "fix_hints": list(item.fix_hints),
        "project_id": item.project_id,
        "category": item.category,
        "tags": list(item.tags),
        "timing_seconds": item.timing_seconds,
        "locations": {
            "source": _entity_location(item.source),
            "target": _entity_location(item.target),
        },
        "result_id": item.result_id,
    }
    if item.activation_source is not None:
        out["activation_source"] = item.activation_source
    out.update(item.extras)
    return out


def _matching_to_dict(section: MatchingSection) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "matches": [dict(v) for v in section.matches],
    }
    if section.matching_config:
        out["matching_config"] = dict(section.matching_config)
    return out


def _results_summary_to_dict(summary: Any) -> Dict[str, Any]:
    return {
        "results_total": summary.results_total,
        "status_counts": dict(summary.status_counts),
        "severity_counts": dict(summary.severity_counts),
        "category_counts": dict(summary.category_counts),
        "top_rules": [dict(v) for v in summary.top_rules],
        "top_source_files": [dict(v) for v in summary.top_source_files],
        "timings": dict(summary.timings) if summary.timings is not None else None,
    }


def _target_to_dict(target: TargetReport) -> Dict[str, Any]:
    return {
        "target_id": target.target_id,
        "display_name": target.display_name,
        "source_root": target.source_root,
        "target_path": target.target_path,
        "tags": list(target.tags),
        "mode": target.mode,
        "matching": _matching_to_dict(target.matching),
        "results": [_result_to_dict(r) for r in target.results],
        "summary": _results_summary_to_dict(target.summary),
        "artifacts": [dict(v) for v in target.artifacts],
        "exit_code": target.exit_code,
    }


def to_legacy_schema_v2(doc: ReportDocument) -> Dict[str, Any]:
    """Serialize typed IR document to legacy schema-v2 dict layout."""
    run: Dict[str, Any] = {
        "generated_at": doc.run.generated_at,
        "source_path": doc.run.source_path,
        "reference_modules": list(doc.run.reference_modules),
        "config_snapshot": doc.run.config_snapshot,
        "config_fingerprint": doc.run.config_fingerprint,
        "tool_version": doc.run.tool_version,
        "mode": doc.run.mode,
    }
    summary: Dict[str, Any] = {
        "targets_total": doc.summary.targets_total or 0,
        "targets_failed": doc.summary.targets_failed or 0,
        "targets_passed": doc.summary.targets_passed or 0,
        "results": _results_summary_to_dict(doc.summary.results),
    }
    return {
        "schema_version": doc.schema_version,
        "framework_version": doc.framework_version,
        "generated_at": doc.generated_at,
        "run": run,
        "targets": [_target_to_dict(t) for t in doc.targets],
        "summary": summary,
        "exit_code": doc.exit_code,
    }
