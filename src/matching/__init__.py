from __future__ import annotations

from typing import Dict, List

from src.entities import EntityIndex

from .engine import match_entities as _match_entities
from .engine import run_matching as _run_matching
from .metrics import (
    ast_similarity,
    doc_similarity,
    module_distance,
    module_similarity,
    name_similarity,
)
from .models import Candidate, MatchingConfig, MatchResult, MatchStatus


def run_matching(
    source_index: EntityIndex,
    target_index: EntityIndex,
    config: MatchingConfig,
) -> tuple[List[MatchResult], Dict[str, MatchResult]]:
    # Keep facade-level indirection so monkeypatching src.matching.ast_similarity
    # affects matching behavior exactly as before decomposition.
    return _run_matching(
        source_index,
        target_index,
        config,
        ast_similarity_fn=ast_similarity,
        module_similarity_fn=module_similarity,
        module_distance_fn=module_distance,
        name_similarity_fn=name_similarity,
    )


def match_entities(
    source_index: EntityIndex,
    target_index: EntityIndex,
    config: MatchingConfig,
) -> List[MatchResult]:
    return _match_entities(
        source_index,
        target_index,
        config,
        ast_similarity_fn=ast_similarity,
        module_similarity_fn=module_similarity,
        module_distance_fn=module_distance,
        name_similarity_fn=name_similarity,
    )


__all__ = [
    "MatchStatus",
    "Candidate",
    "MatchResult",
    "MatchingConfig",
    "module_similarity",
    "module_distance",
    "ast_similarity",
    "name_similarity",
    "doc_similarity",
    "run_matching",
    "match_entities",
]
