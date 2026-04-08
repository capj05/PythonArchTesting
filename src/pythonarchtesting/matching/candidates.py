from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pythonarchtesting.entities import Entity, EntityIndex

from .metrics import (
    class_name_from_qualname,
    doc_similarity,
    method_first_param_mismatch,
)
from .models import Candidate


def _sort_candidates(candidates: List[Candidate]) -> List[Candidate]:
    return sorted(
        candidates,
        key=lambda c: (
            -c.confidence,
            -c.breakdown.get("mod", 0.0),
            c.breakdown.get("module_distance", 10**9),
            c.target_id,
        ),
    )


def _build_candidate(
    target: Entity,
    confidence: float,
    breakdown: Dict[str, float],
    tie_break: Tuple[Any, ...],
) -> Candidate:
    return Candidate(
        target_id=target.canonical_id,
        confidence=confidence,
        breakdown=breakdown,
        tie_break=tie_break,
    )


def _apply_cap(items: list[Any], cap: int) -> list[Any]:
    if cap <= 0:
        return items
    return items[:cap]


def _explicit_target_match(
    source: Entity, target_index: EntityIndex
) -> tuple[Optional[Entity], Optional[Dict[str, Any]]]:
    explicit = source.surface_meta.get("explicit_target")
    if not explicit:
        return None, None

    module_path = explicit.get("module_path")
    qualname = explicit.get("qualname")
    kind = explicit.get("kind")
    signature_key = explicit.get("signature_key")

    missing = [
        k
        for k in ("module_path", "qualname", "kind", "signature_key")
        if explicit.get(k) is None
    ]
    if missing:
        reason = {
            "code": "explicit_target_not_found",
            "message": "Explicit target mapping missing fields.",
            "evidence": {"missing": missing, "explicit_target": explicit},
        }
        return None, reason

    core_key = f"{module_path}:{qualname}:{kind}:{signature_key}"
    candidates = target_index.by_core.get(core_key, [])
    if len(candidates) == 1:
        return candidates[0], {
            "code": "explicit_target_hit",
            "message": "Explicit target mapping resolved.",
            "evidence": {"core_key": core_key, "target_id": candidates[0].canonical_id},
        }

    reason = {
        "code": "explicit_target_not_found",
        "message": "Explicit target mapping did not resolve uniquely.",
        "evidence": {"core_key": core_key, "matches": len(candidates)},
    }
    return None, reason


def _stage2_candidates(
    source: Entity,
    target_index: EntityIndex,
    *,
    ast_similarity_fn: Any,
    module_similarity_fn: Any,
    module_distance_fn: Any,
    name_similarity_fn: Any,
    max_stage2_candidates: int,
) -> List[Candidate]:
    candidates: List[Candidate] = []
    if source.signature_key != "-":
        pool = target_index.by_sig.get((source.kind, source.signature_key), [])
    else:
        pool = target_index.by_name.get((source.kind, source.name), [])

    pool = sorted(
        pool,
        key=lambda target: (
            source.name != target.name,
            module_distance_fn(source.module_path, target.module_path),
            target.canonical_id,
        ),
    )
    pool = _apply_cap(pool, max_stage2_candidates)

    for target in pool:
        if source.signature_key != "-" and target.signature_key != "-":
            if source.signature_key != target.signature_key:
                continue

        ast = ast_similarity_fn(source, target)
        mod = module_similarity_fn(source.module_path, target.module_path)
        name = name_similarity_fn(source.name, target.name)
        confidence = round(0.70 * ast + 0.30 * mod, 6)
        distance = module_distance_fn(source.module_path, target.module_path)
        breakdown = {
            "ast": ast,
            "mod": mod,
            "name": name,
            "doc": 0.0,
            "penalty": 0.0,
            "module_distance": float(distance),
        }
        tie_break = (-confidence, -mod, distance, target.canonical_id)
        candidates.append(_build_candidate(target, confidence, breakdown, tie_break))

    return _sort_candidates(candidates)


def _stage3_candidates(
    source: Entity,
    target_index: EntityIndex,
    seed_candidates: List[Candidate],
    seed_limit: int,
    max_stage3_candidates: int,
    *,
    ast_similarity_fn: Any,
    module_similarity_fn: Any,
    module_distance_fn: Any,
    name_similarity_fn: Any,
) -> List[Candidate]:
    selected_ids = [c.target_id for c in seed_candidates[:seed_limit]]
    name_pool = target_index.by_name.get((source.kind, source.name), [])
    for target in name_pool:
        if target.canonical_id not in selected_ids:
            selected_ids.append(target.canonical_id)

    target_lookup = {e.canonical_id: e for e in target_index.all_sorted}
    selected_targets: list[Entity] = []
    for target_id in selected_ids:
        selected_target: Entity | None = target_lookup.get(target_id)
        if selected_target is not None:
            selected_targets.append(selected_target)

    selected_targets = sorted(
        selected_targets,
        key=lambda target: (
            source.name != target.name,
            module_distance_fn(source.module_path, target.module_path),
            target.canonical_id,
        ),
    )
    selected_targets = _apply_cap(selected_targets, max_stage3_candidates)

    candidates: List[Candidate] = []
    source_doc = source.extras.get("docstring", "") or ""
    source_class = class_name_from_qualname(source.qualname)

    for target in selected_targets:
        ast = ast_similarity_fn(source, target)
        mod = module_similarity_fn(source.module_path, target.module_path)
        structural = round(0.70 * ast + 0.30 * mod, 6)
        name = name_similarity_fn(source.name, target.name)
        target_doc = target.extras.get("docstring", "") or ""
        doc = doc_similarity(source_doc, target_doc)

        penalty = 0.0
        if mod < 0.30:
            penalty += 0.10
        if source.kind == "method":
            target_class = class_name_from_qualname(target.qualname)
            if source_class and target_class and source_class != target_class:
                penalty += 0.05
            if method_first_param_mismatch(source, target):
                penalty += 0.03

        confidence = round(0.55 * structural + 0.30 * name + 0.15 * doc - penalty, 6)
        if confidence < 0.0:
            confidence = 0.0

        distance = module_distance_fn(source.module_path, target.module_path)
        breakdown = {
            "ast": ast,
            "mod": mod,
            "name": name,
            "doc": doc,
            "penalty": penalty,
            "module_distance": float(distance),
        }
        tie_break = (-confidence, -mod, distance, target.canonical_id)
        candidates.append(_build_candidate(target, confidence, breakdown, tie_break))

    return _sort_candidates(candidates)


__all__ = ["_explicit_target_match", "_stage2_candidates", "_stage3_candidates"]
