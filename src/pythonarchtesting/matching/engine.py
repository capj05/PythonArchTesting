from __future__ import annotations

from typing import Any, Callable, Dict, List

from pythonarchtesting.entities import Entity, EntityIndex

from .candidates import _explicit_target_match, _stage2_candidates, _stage3_candidates
from .metrics import ast_similarity, module_distance, module_similarity, name_similarity
from .models import Candidate, MatchingConfig, MatchResult, MatchStatus


def run_matching(
    source_index: EntityIndex,
    target_index: EntityIndex,
    config: MatchingConfig,
    *,
    ast_similarity_fn: Callable[[Entity, Entity], float] = ast_similarity,
    module_similarity_fn: Callable[[str, str], float] = module_similarity,
    module_distance_fn: Callable[[str, str], int] = module_distance,
    name_similarity_fn: Callable[[str, str], float] = name_similarity,
) -> tuple[List[MatchResult], Dict[str, MatchResult]]:
    results: List[MatchResult] = []
    by_source: Dict[str, MatchResult] = {}
    module_similarity_cache: Dict[tuple[str, str], float] = {}
    module_distance_cache: Dict[tuple[str, str], int] = {}
    name_similarity_cache: Dict[tuple[str, str], float] = {}
    ast_similarity_cache: Dict[tuple[str, str], float] = {}

    def _cached_module_similarity(source_module: str, target_module: str) -> float:
        key = (source_module, target_module)
        cached = module_similarity_cache.get(key)
        if cached is not None:
            return cached
        value = module_similarity_fn(source_module, target_module)
        module_similarity_cache[key] = value
        return value

    def _cached_module_distance(source_module: str, target_module: str) -> int:
        key = (source_module, target_module)
        cached = module_distance_cache.get(key)
        if cached is not None:
            return cached
        value = module_distance_fn(source_module, target_module)
        module_distance_cache[key] = value
        return value

    def _cached_name_similarity(a: str, b: str) -> float:
        key = (a, b)
        cached = name_similarity_cache.get(key)
        if cached is not None:
            return cached
        value = name_similarity_fn(a, b)
        name_similarity_cache[key] = value
        return value

    def _cached_ast_similarity(source: Entity, target: Entity) -> float:
        key = (source.canonical_id, target.canonical_id)
        cached = ast_similarity_cache.get(key)
        if cached is not None:
            return cached
        value = ast_similarity_fn(source, target)
        ast_similarity_cache[key] = value
        return value

    for source in source_index.all_sorted:
        reasons: List[Dict[str, Any]] = []

        explicit_target, explicit_reason = _explicit_target_match(source, target_index)
        if explicit_reason is not None:
            reasons.append(explicit_reason)
        if explicit_target is not None:
            explicit_name = _cached_name_similarity(source.name, explicit_target.name)
            explicit_distance = _cached_module_distance(
                source.module_path, explicit_target.module_path
            )
            candidate = Candidate(
                target_id=explicit_target.canonical_id,
                confidence=1.0,
                breakdown={
                    "ast": 1.0,
                    "mod": 1.0,
                    "name": explicit_name,
                    "doc": 0.0,
                    "penalty": 0.0,
                    "module_distance": float(explicit_distance),
                },
                tie_break=(-1.0, -1.0, 0, explicit_target.canonical_id),
            )

            match = MatchResult(
                source_id=source.canonical_id,
                status=MatchStatus.MATCHED,
                target_id=explicit_target.canonical_id,
                confidence=1.0,
                reasons=reasons,
                candidates=[candidate],
            )
            results.append(match)
            by_source[match.source_id] = match
            continue

        core_key = f"{
            source.module_path}:{
            source.qualname}:{
            source.kind}:{
                source.signature_key}"
        stage1_candidates = target_index.by_core.get(core_key, [])
        if len(stage1_candidates) == 1:
            target = stage1_candidates[0]

            stage1_name = _cached_name_similarity(source.name, target.name)
            stage1_distance = _cached_module_distance(
                source.module_path, target.module_path
            )
            candidate = Candidate(
                target_id=target.canonical_id,
                confidence=1.0,
                breakdown={
                    "ast": 1.0,
                    "mod": 1.0,
                    "name": stage1_name,
                    "doc": 0.0,
                    "penalty": 0.0,
                    "module_distance": float(stage1_distance),
                },
                tie_break=(-1.0, -1.0, 0, target.canonical_id),
            )
            reasons.append(
                {
                    "code": "stage1_exact",
                    "message": "Exact core key match.",
                    "evidence": {
                        "core_key": core_key,
                        "target_id": target.canonical_id,
                    },
                }
            )
            match = MatchResult(
                source_id=source.canonical_id,
                status=MatchStatus.MATCHED,
                target_id=target.canonical_id,
                confidence=1.0,
                reasons=reasons,
                candidates=[candidate],
            )
            results.append(match)
            by_source[match.source_id] = match
            continue
        if len(stage1_candidates) > 1:
            reasons.append(
                {
                    "code": "stage1_conflict",
                    "message": "Multiple exact core key matches.",
                    "evidence": {
                        "core_key": core_key,
                        "matches": len(stage1_candidates),
                    },
                }
            )

        stage2_candidates = _stage2_candidates(
            source,
            target_index,
            ast_similarity_fn=_cached_ast_similarity,
            module_similarity_fn=_cached_module_similarity,
            module_distance_fn=_cached_module_distance,
            name_similarity_fn=_cached_name_similarity,
            max_stage2_candidates=config.max_stage2_candidates,
        )
        if not stage2_candidates:
            reasons.append(
                {
                    "code": "stage2_no_candidates",
                    "message": "No stage 2 candidates found.",
                    "evidence": {"source_id": source.canonical_id},
                }
            )

        stage2_best = stage2_candidates[0].confidence if stage2_candidates else 0.0
        stage2_ambiguous = False
        if stage2_candidates and stage2_best >= config.threshold:
            if len(stage2_candidates) > 1:
                if stage2_candidates[1].confidence >= stage2_best - config.delta:
                    stage2_ambiguous = True

        run_stage3 = False
        if stage2_best < config.min_candidate:
            run_stage3 = True
        if stage2_ambiguous and len(stage2_candidates) <= config.max_fuzzy_candidates:
            run_stage3 = True

        final_candidates: List[Candidate]
        if run_stage3:
            stage3_candidates = _stage3_candidates(
                source,
                target_index,
                stage2_candidates,
                config.max_fuzzy_candidates,
                config.max_stage3_candidates,
                ast_similarity_fn=_cached_ast_similarity,
                module_similarity_fn=_cached_module_similarity,
                module_distance_fn=_cached_module_distance,
                name_similarity_fn=_cached_name_similarity,
            )
            if stage3_candidates:
                reasons.append(
                    {
                        "code": "stage3_selected",
                        "message": "Stage 3 fuzzy matching executed.",
                        "evidence": {"candidates": len(stage3_candidates)},
                    }
                )
                final_candidates = stage3_candidates
            else:
                reasons.append(
                    {
                        "code": "stage3_no_candidates",
                        "message": "Stage 3 ran but produced no candidates.",
                        "evidence": {"source_id": source.canonical_id},
                    }
                )
                final_candidates = stage2_candidates
        else:
            reasons.append(
                {
                    "code": "stage3_not_run",
                    "message": "Stage 3 not executed.",
                    "evidence": {"source_id": source.canonical_id},
                }
            )
            final_candidates = stage2_candidates

        if final_candidates:
            top = final_candidates[0]
            best = top.confidence
            target_id = top.target_id
        else:
            best = 0.0
            target_id = None

        status = MatchStatus.UNMATCHED
        if not final_candidates:
            reasons.append(
                {
                    "code": "unmatched_no_candidates",
                    "message": "No candidates available.",
                    "evidence": {"source_id": source.canonical_id},
                }
            )
        elif best < config.min_candidate:
            reasons.append(
                {
                    "code": "low_confidence_below_threshold",
                    "message": "Best candidate below minimum confidence.",
                    "evidence": {
                        "best": best,
                        "min_candidate": config.min_candidate,
                    },
                }
            )
            status = MatchStatus.UNMATCHED
        elif best < config.threshold:
            reasons.append(
                {
                    "code": "low_confidence_below_threshold",
                    "message": "Best candidate below match threshold.",
                    "evidence": {
                        "best": best,
                        "threshold": config.threshold,
                    },
                }
            )
            status = MatchStatus.LOW_CONFIDENCE
        else:
            if (
                len(final_candidates) > 1
                and final_candidates[1].confidence >= best - config.delta
            ):
                reasons.append(
                    {
                        "code": "ambiguous_competitor_within_delta",
                        "message": "Competing candidate within delta.",
                        "evidence": {
                            "best": best,
                            "delta": config.delta,
                            "competitor": final_candidates[1].confidence,
                        },
                    }
                )
                status = MatchStatus.AMBIGUOUS
            else:
                status = MatchStatus.MATCHED

        if status in {MatchStatus.MATCHED, MatchStatus.LOW_CONFIDENCE}:
            if stage2_candidates and final_candidates is stage2_candidates:
                reasons.append(
                    {
                        "code": "stage2_selected",
                        "message": "Selected by stage 2 structural matching.",
                        "evidence": {"best": best},
                    }
                )

        match = MatchResult(
            source_id=source.canonical_id,
            status=status,
            target_id=target_id,
            confidence=best,
            reasons=reasons,
            candidates=final_candidates[: config.top_n],
        )
        results.append(match)
        by_source[match.source_id] = match

    return results, by_source


def match_entities(
    source_index: EntityIndex,
    target_index: EntityIndex,
    config: MatchingConfig,
    *,
    ast_similarity_fn: Callable[[Entity, Entity], float] = ast_similarity,
    module_similarity_fn: Callable[[str, str], float] = module_similarity,
    module_distance_fn: Callable[[str, str], int] = module_distance,
    name_similarity_fn: Callable[[str, str], float] = name_similarity,
) -> List[MatchResult]:
    results, _ = run_matching(
        source_index,
        target_index,
        config,
        ast_similarity_fn=ast_similarity_fn,
        module_similarity_fn=module_similarity_fn,
        module_distance_fn=module_distance_fn,
        name_similarity_fn=name_similarity_fn,
    )
    return results


__all__ = ["run_matching", "match_entities"]
