from __future__ import annotations

import inspect
import json
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from typing import Any

from pythonarchtesting.entities import DeclarationEntry, Entity
from pythonarchtesting.rules.compilation.common import (
    build_invalid_param_sentinel_rule,
    canonicalize_payload,
    declaration_evidence,
)
from pythonarchtesting.rules.declaration import core as marker_helpers

_SUPPORTED_DECLARATION_KINDS = frozenset(
    {
        "architecture_entry",
        "module_interface",
        "does_not_have",
        "enforce_flow",
        "enforce_layers",
        "forbid_cycles",
        "enforce_reference_calls",
        "is_runtime_singleton",
        "enforce_runtime_observer",
        "require_runtime_delegation",
        "require_runtime_members",
        "forbid_runtime_members",
        "is_runtime_concrete_class",
        "is_runtime_abstract_class",
        "implements_runtime_protocol",
        "forbid_foreign_writes",
        "forbid_private_access",
        "forbid_imports",
        "forbid_runtime_calls",
        "forbid_runtime_imports",
        "forbid_runtime_instantiation",
        "flow",
        "exact_type",
        "inherits_directly_from",
        "implements_protocol",
        "is_abstract_class",
        "is_abstract_method",
        "is_concrete_class",
        "is_enum",
        "is_final_class",
        "is_final_method",
        "is_non_abstract_method",
        "is_non_final_class",
        "is_non_final_method",
        "not_subclass_of",
        "required_attribute",
        "required_constructor",
        "required_entity_signature",
        "required_factory",
        "require_member_set",
        "require_method_set",
        "require_runtime_calls",
        "required_method",
        "subclass_of",
    }
)
_INVALID_ANNOTATION_ISSUES = frozenset(
    {"container", "metadata", "surface", "unknown_metadata"}
)
_DEDUPE_DECLARATION_KINDS = frozenset(
    {
        "architecture_entry",
        "module_interface",
        "does_not_have",
        "enforce_flow",
        "enforce_layers",
        "forbid_cycles",
        "enforce_reference_calls",
        "is_runtime_singleton",
        "enforce_runtime_observer",
        "require_runtime_delegation",
        "require_runtime_members",
        "forbid_runtime_members",
        "is_runtime_concrete_class",
        "is_runtime_abstract_class",
        "implements_runtime_protocol",
        "forbid_foreign_writes",
        "forbid_private_access",
        "forbid_imports",
        "forbid_runtime_calls",
        "forbid_runtime_imports",
        "forbid_runtime_instantiation",
        "exact_type",
        "inherits_directly_from",
        "implements_protocol",
        "is_abstract_class",
        "is_abstract_method",
        "is_concrete_class",
        "is_enum",
        "is_final_class",
        "is_final_method",
        "is_non_abstract_method",
        "is_non_final_class",
        "is_non_final_method",
        "not_subclass_of",
        "required_attribute",
        "required_constructor",
        "required_entity_signature",
        "required_factory",
        "require_member_set",
        "require_method_set",
        "require_runtime_calls",
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


def invalid_annotation_evidence(source_entity: Entity, entry: DeclarationEntry) -> Any:
    """The evidence that ``entry``, a marker annotation the extractor could not
    read as a declaration (``is_invalid_annotation_declaration``), was left
    out of compilation."""
    payload = {
        "declaration": entry.kind,
        "issue": "invalid_declaration",
        "raw": entry.raw,
        "unsupported": entry.unsupported,
        "base_annotation": entry.base_annotation,
        "container": entry.container,
    }
    return declaration_evidence(
        source_entity,
        entry,
        evidence_type="compiler_invalid_declaration",
        payload=payload,
    )


def compile_declarations(
    source_entities: list[Entity],
    cfg: Any,
    compilers: Mapping[str, Any],
    with_source_entities: Collection[str],
) -> tuple[list[Any], list[Any], list[Any]]:
    """The rules, compiler evidence and compiler results of every declaration
    on ``source_entities`` that one of ``compilers`` (by declaration kind)
    compiles, in entity order. An unreadable declaration gives evidence
    instead; a kind no compiler handles is skipped. Compilers of the kinds in
    ``with_source_entities`` also get every source entity."""
    rules: list[Any] = []
    compiler_evidence: list[Any] = []
    compiler_results: list[Any] = []

    for source_entity in source_entities:
        declarations = normalize_declaration_entries(source_entity)
        valid_declarations: list[DeclarationEntry] = []

        for declaration in declarations:
            compiler = compilers.get(declaration.kind)
            if is_invalid_annotation_declaration(declaration):
                compiler_evidence.append(
                    invalid_annotation_evidence(source_entity, declaration)
                )
                continue
            if compiler is None:
                continue
            valid_declarations.append(declaration)

        for declaration, rule_id_suffix in zip(
            valid_declarations,
            declaration_rule_id_suffixes(valid_declarations),
        ):
            compiler = compilers[declaration.kind]
            compiler_kwargs: dict[str, Any] = {"rule_id_suffix": rule_id_suffix}
            if declaration.kind in with_source_entities:
                compiler_kwargs["source_entities"] = source_entities
            compiled_rules, evidence_items, results = compiler(
                source_entity,
                declaration,
                cfg,
                **compiler_kwargs,
            )
            rejected = _reject_unknown_params(
                source_entity, declaration, compiled_rules, rule_id_suffix
            )
            if rejected is not None:
                compiled_rules, unknown_evidence, results = rejected
                evidence_items = [*evidence_items, *unknown_evidence]
            rules.extend(compiled_rules)
            compiler_evidence.extend(evidence_items)
            compiler_results.extend(results)

    return rules, compiler_evidence, compiler_results


# Keys the extraction adds to a declaration's params besides its arguments:
# the source text of a protocol and whether ``flow`` named its variable.
_DERIVED_PARAMS = frozenset({"protocol_expr", "variable_explicit"})
# The prefix of invalid declarations where it is not ``<code>/<marker>/
# invalid_declaration``.
_INVALID_SUFFIX = {"required_factory": "invalid_param"}


def marker_keywords(kind: str) -> list[str]:
    """The keyword arguments marker ``kind`` takes, in signature order: every
    parameter of its helper except a ``*names`` one."""
    helper = getattr(marker_helpers, kind, None)
    if helper is None:
        return []
    return [
        name
        for name, param in inspect.signature(helper).parameters.items()
        if param.kind is not inspect.Parameter.VAR_POSITIONAL
    ]


def _accepted_params(kind: str) -> frozenset[str]:
    """The params keys a declaration of ``kind`` may have: its keywords, its
    ``*names`` parameter (filled from positional arguments) and the keys the
    extraction derives."""
    helper = getattr(marker_helpers, kind)
    return frozenset(inspect.signature(helper).parameters) | _DERIVED_PARAMS


def _reject_unknown_params(
    source_entity: Entity,
    declaration: DeclarationEntry,
    compiled_rules: Sequence[Any],
    rule_id_suffix: str,
) -> tuple[list[Any], list[Any], list[Any]] | None:
    """The dropped declaration when it has a keyword its marker does not take,
    else ``None``.

    A misspelt keyword would otherwise leave the option it meant at its
    default without a word. Only a declaration that compiled to rules of its
    own is dropped: one its compiler already refused keeps that report, and
    one that compiles to no rule (``flow``, a misplaced marker) has no result
    to replace. The sentinel takes the marker's prefix for invalid
    declarations from the rule it replaces.
    """
    kind = declaration.kind
    if not compiled_rules or not hasattr(marker_helpers, kind):
        return None
    if any(rule.rule_type == "compiler_invalid_param" for rule in compiled_rules):
        return None
    accepted = _accepted_params(kind)
    unknown = sorted(key for key in declaration.params if key not in accepted)
    if not unknown:
        return None
    own = next((rule for rule in compiled_rules if rule.name == kind), None)
    rule_id = (own or compiled_rules[0]).rule_id
    if rule_id_suffix and rule_id.endswith(rule_id_suffix):
        rule_id = rule_id[: -len(rule_id_suffix)]
    code = "/".join(rule_id.split("/")[:2])
    prefix = f"{code}/{_INVALID_SUFFIX.get(kind, 'invalid_declaration')}"
    takes = marker_keywords(kind)
    param = unknown[0]
    reason = f"unknown parameter {param!r}; {kind} takes " + ", ".join(takes)
    sentinel = build_invalid_param_sentinel_rule(
        source_entity,
        decorator_name=kind,
        rule_id_prefix=prefix,
        param=param,
        value=declaration.params[param],
        valid=sorted(takes),
        reason=reason,
        rule_id_suffix=rule_id_suffix,
    )
    evidence = declaration_evidence(
        source_entity,
        declaration,
        evidence_type="compiler_invalid_param",
        payload={
            "declaration": kind,
            "issue": "unknown_param",
            "param": param,
            "unknown": unknown,
            "value": declaration.params[param],
            "valid": sorted(takes),
            "reason": reason,
        },
    )
    return [sentinel], [evidence], []


def in_rule_order(
    rules: list[Any], compiler_evidence: list[Any], compiler_results: list[Any]
) -> tuple[list[Any], list[Any], list[Any]]:
    """The compiled rules and results sorted by rule id and source entity, so
    that the output does not depend on the order entities were read in; the
    evidence keeps its order."""
    rules = sorted(rules, key=lambda r: (r.rule_id, r.selector.source_entity_id))
    compiler_results = sorted(
        compiler_results, key=lambda r: (r.rule_id, r.source_entity_id)
    )
    return rules, compiler_evidence, compiler_results


__all__ = [
    "compile_declarations",
    "declaration_rule_id_suffixes",
    "in_rule_order",
    "invalid_annotation_evidence",
    "declaration_rule_id_suffixes",
    "is_invalid_annotation_declaration",
    "normalize_declaration_entries",
]
