"""Assisted pairing: a mapping someone proposed, checked before it is used.

The automatic matching pairs reference and target entities by name, module,
signature and code. A submission organised differently (other module names,
rewritten bodies) can leave entities unpaired, and then every rule on them
reports ``required_target_missing``. A mapping file names the pairs instead,
typically proposed by an LLM client from the candidates the report lists:

    {"pairs": {"controller": "handler",
               "controller.handle_order": "handler.handle_order"}}

or, for several targets, ``{"targets": {"<target id>": {"pairs": {...}}}}``.
A pair of modules pairs their entities with the same qualified name and kind.

Every pair is checked: both entities exist, they are of the same kind, the
target's function can be called the way the reference's is, and an entity
the matching paired on its own keeps its pair. An applied pair is marked
``assisted_mapping`` in the match's reasons, a refused one
``assisted_mapping_rejected``, with why.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Optional

from pythonarchtesting.entities import Entity, EntityIndex, SignatureInfo

from .models import Candidate, MatchResult, MatchStatus

ROOT = "__init__"
_CALLABLE = frozenset({"function", "method"})


def dotted_name(entity: Entity) -> str:
    """The name a mapping uses: ``module`` or ``module.Qual.name``."""
    if entity.kind == "module":
        return entity.module_path or ROOT
    if not entity.module_path:
        return f"{ROOT}.{entity.qualname}"
    return f"{entity.module_path}.{entity.qualname}"


def load_mapping(path: Path) -> dict[str, dict[str, str]]:
    """``{target id or "*": {reference name: target name}}`` from a mapping file."""
    return mapping_from_data(json.loads(path.read_text(encoding="utf-8")))


def mapping_from_data(data: Any) -> dict[str, dict[str, str]]:
    """The same as ``load_mapping``, from data already parsed."""
    if not isinstance(data, dict):
        raise ValueError("a mapping file holds a JSON object")
    found: dict[str, dict[str, str]] = {}
    if "pairs" in data:
        found["*"] = _pairs(data["pairs"], "pairs")
    targets = data.get("targets") or {}
    if not isinstance(targets, dict):
        raise ValueError("targets must map target ids to {'pairs': ...}")
    for target_id, entry in targets.items():
        if not isinstance(entry, dict) or "pairs" not in entry:
            raise ValueError(f"targets.{target_id} needs 'pairs'")
        found[str(target_id)] = _pairs(entry["pairs"], f"targets.{target_id}.pairs")
    if not found:
        raise ValueError("a mapping file needs 'pairs' or 'targets'")
    return found


def _pairs(raw: Any, where: str) -> dict[str, str]:
    if not isinstance(raw, dict) or not all(
        isinstance(k, str) and isinstance(v, str) and k and v for k, v in raw.items()
    ):
        raise ValueError(f"{where} must map reference names to target names")
    return dict(raw)


def signature_compatible(
    source: SignatureInfo | None, target: SignatureInfo | None
) -> bool:
    """Whether the target accepts the positional arguments the reference takes."""
    if source is None or target is None:
        return True
    given = source.posonly + source.pos
    accepted = target.posonly + target.pos
    required = accepted - target.defaults
    # A keyword-only parameter without a default must be passed by name; the
    # reference's callers pass only as many as the reference itself demands.
    required_kw = target.kwonly - target.kw_defaults
    source_kw = source.kwonly - source.kw_defaults
    return (
        required <= given
        and (target.vararg or given <= accepted)
        and required_kw <= source_kw
    )


def _by_name(index: EntityIndex) -> dict[str, list[Entity]]:
    found: dict[str, list[Entity]] = {}
    for entity in index.all_sorted:
        found.setdefault(dotted_name(entity), []).append(entity)
    return found


def _problem(source: Entity, target: Entity) -> Optional[str]:
    if source.kind != target.kind:
        return f"kind differs: the reference's is a {source.kind}, the target's a {target.kind}"
    if source.kind in _CALLABLE and not signature_compatible(
        source.signature, target.signature
    ):
        return "signature: the target cannot be called with the reference's arguments"
    return None


def _pick(entities: list[Entity], kind: Optional[str] = None) -> Optional[Entity]:
    chosen = [e for e in entities if kind is None or e.kind == kind]
    return chosen[0] if len(chosen) == 1 else None


def unknown_names(pairs: Mapping[str, str], source_index: EntityIndex) -> list[str]:
    """The reference names in ``pairs`` that name nothing in the reference."""
    known = _by_name(source_index)
    return sorted(name for name in pairs if name not in known)


def apply_mapping(
    results: list[MatchResult],
    by_source: dict[str, MatchResult],
    source_index: EntityIndex,
    target_index: EntityIndex,
    pairs: Mapping[str, str],
) -> tuple[list[MatchResult], dict[str, MatchResult]]:
    """``results`` with the checked ``pairs`` applied; see the module docstring."""
    sources = _by_name(source_index)
    targets = _by_name(target_index)
    updated = dict(by_source)

    def note(source: Entity, code: str, message: str, evidence: dict[str, Any]) -> None:
        current = updated[source.canonical_id]
        reason = {"code": code, "message": message, "evidence": evidence}
        updated[source.canonical_id] = replace(
            current, reasons=[*current.reasons, reason]
        )

    def pair(source: Entity, target: Entity, via: str) -> None:
        current = updated.get(source.canonical_id)
        evidence = {"pair": via, "target_id": target.canonical_id}
        if current is None:
            return
        if current.status == MatchStatus.MATCHED:
            if current.target_id != target.canonical_id:
                note(
                    source,
                    "assisted_mapping_rejected",
                    "the matching paired this entity on its own; a mapping never "
                    "overrides that",
                    evidence,
                )
            return
        if source.kind != target.kind:
            note(
                source,
                "assisted_mapping_rejected",
                str(_problem(source, target)),
                evidence,
            )
            return
        if target.kind != "module":
            taken = next(
                (
                    other
                    for other in updated.values()
                    if other.status == MatchStatus.MATCHED
                    and other.target_id == target.canonical_id
                ),
                None,
            )
            if taken is not None:
                note(
                    source,
                    "assisted_mapping_rejected",
                    f"the target entity is already paired with {taken.source_id}",
                    evidence,
                )
                return
        problem = _problem(source, target)
        if problem is not None:
            note(source, "assisted_mapping_rejected", problem, evidence)
            return
        candidate = Candidate(
            target_id=target.canonical_id,
            confidence=1.0,
            breakdown={"assisted": 1.0},
            tie_break=(-1.0, -1.0, 0, target.canonical_id),
        )
        updated[source.canonical_id] = replace(
            current,
            status=MatchStatus.MATCHED,
            target_id=target.canonical_id,
            confidence=1.0,
            reasons=[
                *current.reasons,
                {
                    "code": "assisted_mapping",
                    "message": "Paired by a checked mapping (assisted pairing).",
                    "evidence": evidence,
                },
            ],
            candidates=[candidate, *current.candidates],
        )

    def by_mapping(entity: Entity) -> bool:
        current = updated.get(entity.canonical_id)
        return current is not None and any(
            reason.get("code") == "assisted_mapping" for reason in current.reasons
        )

    def is_module_pair(item: tuple[str, str]) -> bool:
        return any(e.kind == "module" for e in sources.get(item[0]) or [])

    # Entity pairs first: a pair the mapping names explicitly wins over the
    # same-named twin a module pair implies.
    for reference_name, target_name in sorted(
        sorted(pairs.items()), key=is_module_pair
    ):
        found = sources.get(reference_name) or []
        if not found:
            continue  # the reference has no such entity: nothing to pair
        modules = [e for e in found if e.kind == "module"]
        if modules:
            source_module = modules[0]
            target_module = _pick(targets.get(target_name) or [], "module")
            if target_module is None:
                note(
                    source_module,
                    "assisted_mapping_rejected",
                    f"the target has no module {target_name!r}",
                    {"pair": f"{reference_name} -> {target_name}"},
                )
                continue
            via = f"{reference_name} -> {target_name}"
            pair(source_module, target_module, via)
            prefix = "" if reference_name == ROOT else reference_name
            for entity in source_index.all_sorted:
                if entity.kind == "module" or entity.module_path != prefix:
                    continue
                twin = _pick(
                    targets.get(f"{target_name}.{entity.qualname}") or [], entity.kind
                )
                if twin is not None and not by_mapping(entity):
                    pair(entity, twin, via)
            continue
        source = found[0]
        target = _pick(targets.get(target_name) or [])
        if target is None:
            note(
                source,
                "assisted_mapping_rejected",
                f"the target has no single entity {target_name!r}",
                {"pair": f"{reference_name} -> {target_name}"},
            )
            continue
        pair(source, target, f"{reference_name} -> {target_name}")

    new_results = [updated[result.source_id] for result in results]
    return new_results, {result.source_id: result for result in new_results}


__all__ = [
    "apply_mapping",
    "unknown_names",
    "dotted_name",
    "load_mapping",
    "mapping_from_data",
    "signature_compatible",
]
