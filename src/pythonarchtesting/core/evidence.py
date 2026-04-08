"""
Evidence collection functions extracted from rules.py.

This module contains functions for collecting and caching evidence
during rule evaluation, with explicit inputs and outputs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Literal, Tuple

from pythonarchtesting.core.models import EvalContext, Evidence
from pythonarchtesting.entities import Entity

EvidenceRole = Literal["source", "target"]


def canonicalize_payload(value: Any) -> Any:
    """Canonicalize a payload value for consistent hashing."""
    if isinstance(value, dict):
        return {k: canonicalize_payload(value[k]) for k in sorted(value.keys())}
    if isinstance(value, (list, tuple)):
        items = [canonicalize_payload(item) for item in value]

        def _canonical_json(v: Any) -> str:
            return json.dumps(
                v, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            )

        return sorted(items, key=_canonical_json)

    def _safe_json_value(value: Any) -> Any:
        try:
            json.dumps(value)
            return value
        except TypeError:
            return repr(value)

    return _safe_json_value(value)


def evidence_id(type_: str, payload: Dict[str, Any]) -> str:
    """Generate evidence ID from type and payload."""

    def _canonical_json(value: Any) -> str:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )

    canonical = _canonical_json(
        {"type": type_, "payload": canonicalize_payload(payload)}
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _record_stat(ctx: EvalContext, key: str) -> None:
    """Record evidence statistics."""
    ctx.evidence_stats[key] = ctx.evidence_stats.get(key, 0) + 1


def _store_evidence(
    ctx: EvalContext,
    key: Tuple[str, str, str],
    evidence: Evidence,
) -> Evidence:
    """Store evidence in context cache."""
    ctx.evidence_store[key] = evidence
    return evidence


def _entity_for_role(
    ctx: EvalContext, entity_id: str | None, role: EvidenceRole
) -> Entity | None:
    """Get entity by ID and role."""
    if entity_id is None:
        return None
    if role == "source":
        return ctx.source_by_id.get(entity_id)
    return ctx.target_by_id.get(entity_id)


def _location_from_entity(entity: Entity | None) -> Dict[str, Any] | None:
    """Extract location information from entity."""
    if entity is None:
        return None
    return {"filepath": entity.filepath_rel, "lineno": entity.lineno}


def get_source_location(
    ctx: EvalContext,
    entity_id: str,
    role: EvidenceRole,
) -> Evidence:
    """Get source location evidence for an entity."""
    key = ("source_location", entity_id, role)
    cached = ctx.evidence_store.get(key)
    if cached is not None:
        return cached

    entity = _entity_for_role(ctx, entity_id, role)
    payload = {
        "filepath": entity.filepath_rel if entity else None,
        "lineno": entity.lineno if entity else None,
    }
    evidence = Evidence(
        evidence_id=evidence_id("source_location", payload),
        type="source_location",
        source="filesystem",
        role=role,
        entity_id=entity_id,
        payload=canonicalize_payload(payload),
        location=_location_from_entity(entity),
    )
    _record_stat(ctx, "source_location")
    return _store_evidence(ctx, key, evidence)


def get_ast_signature(
    ctx: EvalContext,
    entity_id: str,
    role: EvidenceRole,
) -> Evidence:
    """Get AST signature evidence for an entity."""
    key = ("ast_signature", entity_id, role)
    cached = ctx.evidence_store.get(key)
    if cached is not None:
        return cached

    entity = _entity_for_role(ctx, entity_id, role)
    signature = entity.signature if entity else None
    payload = {
        "posonly": signature.posonly if signature else 0,
        "pos": signature.pos if signature else 0,
        "vararg": signature.vararg if signature else False,
        "kwonly": signature.kwonly if signature else 0,
        "kwarg": signature.kwarg if signature else False,
        "defaults": signature.defaults if signature else 0,
        "kw_defaults": signature.kw_defaults if signature else 0,
        "has_signature": signature is not None,
    }
    evidence = Evidence(
        evidence_id=evidence_id("ast_signature", payload),
        type="ast_signature",
        source="ast",
        role=role,
        entity_id=entity_id,
        payload=canonicalize_payload(payload),
        location=_location_from_entity(entity),
    )
    _record_stat(ctx, "ast_signature")
    return _store_evidence(ctx, key, evidence)


def get_ast_annotations(
    ctx: EvalContext,
    entity_id: str,
    role: EvidenceRole,
) -> Evidence:
    """Get AST annotation evidence for an entity."""
    key = ("ast_annotations", entity_id, role)
    cached = ctx.evidence_store.get(key)
    if cached is not None:
        return cached

    entity = _entity_for_role(ctx, entity_id, role)
    annotations = entity.extras.get("annotations") if entity else None
    payload = dict(annotations or {"args": [], "return": None, "has_all": False})
    if entity:
        line_text = entity.extras.get("line_text")
        if line_text is not None:
            payload["line_text"] = line_text
    evidence = Evidence(
        evidence_id=evidence_id("ast_annotations", payload),
        type="ast_annotations",
        source="ast",
        role=role,
        entity_id=entity_id,
        payload=canonicalize_payload(payload),
        location=_location_from_entity(entity),
    )
    _record_stat(ctx, "ast_annotations")
    return _store_evidence(ctx, key, evidence)


__all__ = [
    "canonicalize_payload",
    "evidence_id",
    "get_source_location",
    "get_ast_signature",
    "get_ast_annotations",
]
