from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pythonarchtesting.matching import (
    Candidate,
    MatchingConfig,
    MatchResult,
    MatchStatus,
)

from ._orchestrator import build_entity_indexes as build_entity_indexes_stage
from ._orchestrator import (
    discover_python_files_for_context,
    resolve_source_module_files_for_context,
)
from ._orchestrator import run_matching as run_matching_stage

if TYPE_CHECKING:  # pragma: no cover
    from ._typing import EntitiesStateLike, MatchStateLike


class ProjectStateEntitiesMixin:
    """Entity extraction and indexing (source/target)."""

    def _discover_python_files(
        self: "EntitiesStateLike", root_path: Path
    ) -> list[Path]:
        self._ensure_context_config()
        return discover_python_files_for_context(self._context, root_path)

    def _resolve_source_module_files(
        self: "EntitiesStateLike", module_path: str
    ) -> list[Path]:
        self._ensure_context_config()
        return resolve_source_module_files_for_context(
            self._context,
            module_path,
            self.add_validation_result,
        )

    def build_entity_indexes(self: "EntitiesStateLike") -> None:
        self._ensure_context_config()
        self._stores.entities.reset()
        self._stores.matches.reset()
        self._stores.rules.reset()
        build_entity_indexes_stage(
            self._context,
            self._stores,
            self._services,
            self.add_validation_result,
        )

    def run_matching(self: "EntitiesStateLike") -> None:
        self._ensure_context_config()
        self._stores.matches.reset()
        run_matching_stage(self._context, self._stores)

    def _apply_legacy_fallback(
        self: "MatchStateLike",
        results: list[MatchResult],
        by_source: dict[str, MatchResult],
        config: MatchingConfig,
    ) -> tuple[list[MatchResult], dict[str, MatchResult]]:
        _ = config
        if not self.target_index:
            return results, by_source

        updated_results: list[MatchResult] = []
        updated_by_source = dict(by_source)

        for match in results:
            if match.status != MatchStatus.UNMATCHED:
                updated_results.append(match)
                continue

            source_entity = self.source_by_id.get(match.source_id)
            if source_entity is None:
                updated_results.append(match)
                continue

            candidates = self.target_index.by_name.get(
                (source_entity.kind, source_entity.name), []
            )
            if not candidates:
                updated_results.append(match)
                continue

            target_entity = candidates[0]
            confidence = 0.60
            legacy_candidate = Candidate(
                target_id=target_entity.canonical_id,
                confidence=confidence,
                breakdown={"legacy_name_match": 1.0},
                tie_break=(-confidence, target_entity.canonical_id),
            )

            reasons = list(match.reasons)
            reasons.append(
                {
                    "code": "legacy_fallback_used",
                    "message": "Legacy name-based fallback applied.",
                    "evidence": {
                        "source_id": match.source_id,
                        "target_id": target_entity.canonical_id,
                        "function_name": source_entity.name,
                    },
                }
            )

            updated_match = MatchResult(
                source_id=match.source_id,
                status=match.status,
                target_id=match.target_id,
                confidence=match.confidence,
                reasons=reasons,
                candidates=list(match.candidates) + [legacy_candidate],
            )
            updated_results.append(updated_match)
            updated_by_source[match.source_id] = updated_match

        return updated_results, updated_by_source
