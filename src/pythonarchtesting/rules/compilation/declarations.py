from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from pythonarchtesting.entities import DeclarationEntry
from pythonarchtesting.rules.compilation.common import canonicalize_payload

_SUPPORTED_DECLARATION_KINDS = frozenset(
    {
        "does_not_have",
        "enforce_flow",
        "forbid_imports",
        "flow",
        "implements_protocol",
        "required_attribute",
        "required_constructor",
        "required_entity_signature",
        "required_factory",
        "required_method",
        "subclass_of",
    }
)
_INVALID_ANNOTATION_ISSUES = frozenset(
    {"container", "metadata", "surface", "unknown_metadata"}
)
_DEDUPE_DECLARATION_KINDS = frozenset(
    {
        "does_not_have",
        "enforce_flow",
        "forbid_imports",
        "implements_protocol",
        "required_attribute",
        "required_constructor",
        "required_entity_signature",
        "required_factory",
        "required_method",
        "subclass_of",
    }
)


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _merge_unsupported(
    left: list[dict[str, Any]], right: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*left, *right]:
        key = _json_key(canonicalize_payload(item))
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(item))
    return merged


def _fingerprint(entry: DeclarationEntry) -> str:
    payload = canonicalize_payload(
        {
            "kind": entry.kind,
            "params": entry.params,
            "surface": entry.surface,
            "subject_kind": entry.subject_kind,
            "subject_index": entry.subject_index,
            "subject_name": entry.subject_name,
        }
    )
    return _json_key(payload)


def _can_dedupe(entry: DeclarationEntry) -> bool:
    return (
        entry.kind in _DEDUPE_DECLARATION_KINDS
        and not is_invalid_annotation_declaration(entry)
    )


def normalize_declaration_entries(entity: Any) -> list[DeclarationEntry]:
    entries: list[DeclarationEntry] = []
    for decl in getattr(entity, "annotation_declarations", []) or []:
        entries.append(
            DeclarationEntry(
                kind=str(getattr(decl, "kind", "")),
                params=dict(getattr(decl, "params", {}) or {}),
                unsupported=list(getattr(decl, "unsupported", []) or []),
                lineno=int(getattr(decl, "lineno", 0) or 0),
                col=int(getattr(decl, "col", 0) or 0),
                order=int(getattr(decl, "order", 0) or 0),
                raw=str(getattr(decl, "raw", "") or ""),
                base_annotation=str(getattr(decl, "base_annotation", "") or ""),
                container=str(getattr(decl, "container", "") or ""),
                surface=str(getattr(decl, "surface", "body") or "body"),
                subject_kind=str(getattr(decl, "subject_kind", "") or ""),
                subject_index=(
                    int(subject_index)
                    if (subject_index := getattr(decl, "subject_index", -1)) is not None
                    else -1
                ),
                subject_name=str(getattr(decl, "subject_name", "") or ""),
            )
        )

    entries.sort(key=lambda entry: (entry.lineno, entry.col, entry.order))

    normalized: list[DeclarationEntry] = []
    dedupe_index: dict[str, int] = {}

    for entry in entries:
        if not _can_dedupe(entry):
            normalized.append(entry)
            continue

        fingerprint = _fingerprint(entry)
        existing_index = dedupe_index.get(fingerprint)
        if existing_index is None:
            dedupe_index[fingerprint] = len(normalized)
            normalized.append(entry)
            continue

        existing = normalized[existing_index]
        normalized[existing_index] = replace(
            existing,
            unsupported=_merge_unsupported(existing.unsupported, entry.unsupported),
            raw=existing.raw or entry.raw,
            base_annotation=existing.base_annotation or entry.base_annotation,
            container=existing.container or entry.container,
            surface=existing.surface or entry.surface,
            subject_kind=existing.subject_kind or entry.subject_kind,
            subject_index=(
                existing.subject_index
                if existing.subject_index >= 0
                else entry.subject_index
            ),
            subject_name=existing.subject_name or entry.subject_name,
        )

    return normalized


def is_invalid_annotation_declaration(entry: DeclarationEntry) -> bool:
    if entry.kind == "unknown":
        return True
    if entry.kind not in _SUPPORTED_DECLARATION_KINDS:
        return True
    if entry.kind == "flow" and entry.surface != "statement":
        return True
    return any(
        issue.get("kind") in _INVALID_ANNOTATION_ISSUES for issue in entry.unsupported
    )


def declaration_rule_id_suffixes(
    entries: Sequence[DeclarationEntry],
) -> list[str]:
    counts = Counter(entry.kind for entry in entries)
    seen: Counter[str] = Counter()
    suffixes: list[str] = []

    for entry in entries:
        if counts[entry.kind] <= 1:
            suffixes.append("")
            continue
        suffixes.append(f"/d{seen[entry.kind]}")
        seen[entry.kind] += 1

    return suffixes


__all__ = [
    "declaration_rule_id_suffixes",
    "is_invalid_annotation_declaration",
    "normalize_declaration_entries",
]
