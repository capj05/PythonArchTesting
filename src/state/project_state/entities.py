from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, cast

from src.config.accessors import get_bool
from src.config.data import create_config_from_dict
from src.constants import ValidationConstants
from src.entities import Entity, build_entity_index, sort_entities
from src.entities_extraction import (
    extract_entities_from_ast_with_nonmatchable,
    module_path_from_file,
    root_path_from_module_path,
)
from src.infrastructure.logging import get_logger
from src.matching import (
    Candidate,
    MatchingConfig,
    MatchResult,
    MatchStatus,
    run_matching,
)
from src.state.source_resolution import resolve_source_module_files
from src.state.validation import ValidationResult
from src.util.discovery_utils import discover_python_files
from src.validation_scope import filter_entities_for_scope

if TYPE_CHECKING:  # pragma: no cover
    from src.core.models import Rule, RuleResult

    from ._typing import ProjectStateLike

ValidationStatus = ValidationConstants.ValidationStatus
logger = get_logger(__name__)


class ProjectStateEntitiesMixin:
    """Entity extraction and indexing (source/target)."""

    target_project_path: str | None
    target_module_name: str | None
    validation_scope: str
    reference_modules: list[str]
    source_entities: list[Entity]
    target_entities: list[Entity]
    source_non_matchable_entities: list[Entity]
    target_non_matchable_entities: list[Entity]
    source_by_id: dict[str, Entity]
    target_by_id: dict[str, Entity]
    match_results: list[MatchResult]
    match_by_source_id: dict[str, MatchResult]
    match_registry: dict[str, MatchResult]
    rules: list[Rule]
    rule_results: list[RuleResult]
    source_index: object | None
    target_index: object | None

    def _discover_python_files(self: "ProjectStateLike", root_path: Path) -> list[Path]:
        config = self._active_config()
        target_project_path = self.target_project_path
        if (
            target_project_path
            and root_path == Path(target_project_path)
            and set(config.discovery.included_file_patterns) == {"*.pyi"}
        ):
            raw_config = deepcopy(config.raw or {})
            discovery = raw_config.setdefault("discovery", {})
            discovery["included_file_patterns"] = ["*.py"]
            return cast(
                list[Path],
                discover_python_files(root_path, create_config_from_dict(raw_config)),
            )
        return cast(list[Path], discover_python_files(root_path, config))

    def _resolve_source_module_files(
        self: "ProjectStateLike", module_path: str
    ) -> list[Path]:
        config = self._active_config()
        source_root = Path(str(config.projects.source_path))
        prefer_stub_files = set(config.discovery.included_file_patterns) == {"*.pyi"}
        files, errors = resolve_source_module_files(
            module_path,
            source_root,
            prefer_stub_files=prefer_stub_files,
        )
        if not files and source_root.exists():
            for candidate in self._discover_python_files(source_root):
                resolved_module_path, _ = module_path_from_file(
                    candidate,
                    source_root,
                    None,
                )
                if resolved_module_path == module_path:
                    files.append(candidate)
        if files:
            return cast(list[Path], files)
        for error in errors:
            self.add_validation_result(error)
        return cast(list[Path], files)

    def build_entity_indexes(self: "ProjectStateLike") -> None:
        if not self.target_project_path:
            logger.warning("No target project configured for entity extraction.")
            return

        root_path = Path(self.target_project_path)
        target_module_name = self.target_module_name
        include_nested = get_bool(
            self._active_config(), "matching", "include_nested_functions", False
        )

        self.source_entities = []
        self.target_entities = []
        self.source_non_matchable_entities = []
        self.target_non_matchable_entities = []
        self.source_index = None
        self.target_index = None
        self.source_by_id = {}
        self.target_by_id = {}
        self.match_results = []
        self.match_by_source_id = {}
        self.rules = []
        self.rule_results = []

        target_entities: list[Entity] = []
        target_non_matchable: list[Entity] = []
        for file_path in self._discover_python_files(root_path):
            try:
                file_text = Path(file_path).read_text(
                    encoding="utf-8", errors="replace"
                )
                tree = ast.parse(file_text)
            except SyntaxError as exc:
                error = ValidationResult(
                    status=ValidationStatus.ERROR,
                    description="Syntax error during target entity extraction.",
                    check_type="extraction/syntax_error",
                    src_function_name="",
                    src_package=str(root_path),
                    src_file=str(file_path),
                    src_line_num=getattr(exc, "lineno", None),
                    details={
                        "exception": str(exc),
                        "lineno": getattr(exc, "lineno", None),
                        "offset": getattr(exc, "offset", None),
                    },
                )
                self.add_validation_result(error)
                continue

            matchable, non_matchable = extract_entities_from_ast_with_nonmatchable(
                tree,
                file_text,
                Path(file_path),
                root_path,
                target_module_name,
                role="target",
                include_nested_functions=include_nested,
            )
            target_entities.extend(matchable)
            target_non_matchable.extend(non_matchable)

        self.target_entities = sort_entities(target_entities)
        self.target_non_matchable_entities = sort_entities(target_non_matchable)
        self.target_entities = sort_entities(
            filter_entities_for_scope(self.target_entities, self.validation_scope)
        )
        self.target_non_matchable_entities = sort_entities(
            filter_entities_for_scope(
                self.target_non_matchable_entities, self.validation_scope
            )
        )
        self.target_index = build_entity_index(self.target_entities)
        self.target_by_id = {e.canonical_id: e for e in self.target_entities}

        source_entities: list[Entity] = []
        source_non_matchable: list[Entity] = []
        for module_path in self.reference_modules:
            files = self._resolve_source_module_files(module_path)
            for file_path in files:
                source_root = root_path_from_module_path(module_path, Path(file_path))
                try:
                    file_text = Path(file_path).read_text(
                        encoding="utf-8", errors="replace"
                    )
                    tree = ast.parse(file_text)
                except SyntaxError as exc:
                    error = ValidationResult(
                        status=ValidationStatus.ERROR,
                        description="Syntax error while parsing source module.",
                        check_type="extraction/syntax_error",
                        src_function_name="",
                        src_package=module_path,
                        src_file=str(file_path),
                        src_line_num=getattr(exc, "lineno", None),
                        details={
                            "exception": str(exc),
                            "lineno": getattr(exc, "lineno", None),
                            "offset": getattr(exc, "offset", None),
                        },
                    )
                    self.add_validation_result(error)
                    continue

                matchable, non_matchable = extract_entities_from_ast_with_nonmatchable(
                    tree,
                    file_text,
                    Path(file_path),
                    source_root,
                    None,
                    role="source",
                    include_nested_functions=include_nested,
                )
                source_entities.extend(matchable)
                source_non_matchable.extend(non_matchable)

        self.source_entities = sort_entities(source_entities)
        self.source_non_matchable_entities = sort_entities(source_non_matchable)
        self.source_entities = sort_entities(
            filter_entities_for_scope(self.source_entities, self.validation_scope)
        )
        self.source_non_matchable_entities = sort_entities(
            filter_entities_for_scope(
                self.source_non_matchable_entities, self.validation_scope
            )
        )
        self.source_index = build_entity_index(self.source_entities)
        self.source_by_id = {e.canonical_id: e for e in self.source_entities}

    def run_matching(self: "ProjectStateLike") -> None:
        if not self.source_index or not self.target_index:
            logger.warning("Entity indexes not built; skipping matching.")
            return
        config = MatchingConfig.from_config(self._active_config())
        results, by_source = run_matching(self.source_index, self.target_index, config)
        self.match_results = results
        self.match_by_source_id = by_source
        self.match_registry = dict(by_source)

    def _apply_legacy_fallback(
        self: "ProjectStateLike",
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
