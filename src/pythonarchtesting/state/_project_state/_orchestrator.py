from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from pythonarchtesting.config.accessors import get_bool
from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.constants import ValidationConstants
from pythonarchtesting.entities import Entity, build_entity_index, sort_entities
from pythonarchtesting.entities_extraction import (
    extract_entities_from_ast_with_nonmatchable,
    module_path_from_file,
    root_path_from_module_path,
)
from pythonarchtesting.infrastructure.logging import get_logger
from pythonarchtesting.matching import MatchingConfig
from pythonarchtesting.matching import run_matching as execute_matching
from pythonarchtesting.rules.compilation.orchestrator import (
    compile_rules as compile_entity_rules,
)
from pythonarchtesting.state.source_resolution import resolve_source_module_files
from pythonarchtesting.state.validation import (
    compiler_evidence_to_validation,
    rule_result_to_validation,
)
from pythonarchtesting.util.discovery_utils import discover_python_files
from pythonarchtesting.validation_scope import filter_entities_for_scope

from ._context import ProjectContext
from ._stores import ProjectServices, ProjectStores

ValidationStatus = ValidationConstants.ValidationStatus
logger = get_logger(__name__)


def _require_config(context: ProjectContext) -> Any:
    if context.config is None:
        raise ValueError("ProjectState config must be initialized before analysis.")
    return context.config


def discover_python_files_for_context(
    context: ProjectContext,
    root_path: Path,
) -> list[Path]:
    config = _require_config(context)
    if (
        context.target_project_path
        and root_path == Path(context.target_project_path)
        and set(config.discovery.included_file_patterns) == {"*.pyi"}
    ):
        raw_config = deepcopy(config.raw or {})
        discovery = raw_config.setdefault("discovery", {})
        discovery["included_file_patterns"] = ["*.py"]
        return discover_python_files(root_path, create_config_from_dict(raw_config))
    return discover_python_files(root_path, config)


def resolve_source_module_files_for_context(
    context: ProjectContext,
    module_path: str,
    add_validation_result: Callable[[Any], None],
) -> list[Path]:
    config = _require_config(context)
    source_root = Path(str(config.projects.source_path))
    prefer_stub_files = set(config.discovery.included_file_patterns) == {"*.pyi"}
    files, errors = resolve_source_module_files(
        module_path,
        source_root,
        prefer_stub_files=prefer_stub_files,
    )
    if not files and source_root.exists():
        for candidate in discover_python_files_for_context(context, source_root):
            resolved_module_path, _ = module_path_from_file(
                candidate,
                source_root,
                None,
            )
            if resolved_module_path == module_path:
                files.append(candidate)
    if files:
        return files
    for error in errors:
        add_validation_result(error)
    return files


def build_entity_indexes(
    context: ProjectContext,
    stores: ProjectStores,
    services: ProjectServices,
    add_validation_result: Callable[[Any], None],
) -> None:
    _ = services
    if not context.target_project_path:
        logger.warning("No target project configured for entity extraction.")
        return

    config = _require_config(context)
    root_path = Path(context.target_project_path)
    include_nested = get_bool(config, "matching", "include_nested_functions", False)

    target_entities: list[Entity] = []
    target_non_matchable: list[Entity] = []
    for file_path in discover_python_files_for_context(context, root_path):
        try:
            file_text = Path(file_path).read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(file_text)
        except SyntaxError as exc:
            add_validation_result(
                _syntax_validation(
                    description="Syntax error during target entity extraction.",
                    src_package=str(root_path),
                    src_file=str(file_path),
                    exc=exc,
                )
            )
            continue

        matchable, non_matchable = extract_entities_from_ast_with_nonmatchable(
            tree,
            file_text,
            Path(file_path),
            root_path,
            context.target_module_name,
            role="target",
            include_nested_functions=include_nested,
        )
        target_entities.extend(matchable)
        target_non_matchable.extend(non_matchable)

    stores.entities.target_entities = sort_entities(
        filter_entities_for_scope(
            sort_entities(target_entities), context.validation_scope
        )
    )
    stores.entities.target_non_matchable_entities = sort_entities(
        filter_entities_for_scope(
            sort_entities(target_non_matchable),
            context.validation_scope,
        )
    )
    stores.entities.target_index = build_entity_index(stores.entities.target_entities)
    stores.entities.target_by_id = {
        entity.canonical_id: entity for entity in stores.entities.target_entities
    }

    source_entities: list[Entity] = []
    source_non_matchable: list[Entity] = []
    for module_path in context.reference_modules:
        files = resolve_source_module_files_for_context(
            context,
            module_path,
            add_validation_result,
        )
        for file_path in files:
            source_root = root_path_from_module_path(module_path, Path(file_path))
            try:
                file_text = Path(file_path).read_text(
                    encoding="utf-8", errors="replace"
                )
                tree = ast.parse(file_text)
            except SyntaxError as exc:
                add_validation_result(
                    _syntax_validation(
                        description="Syntax error while parsing source module.",
                        src_package=module_path,
                        src_file=str(file_path),
                        exc=exc,
                    )
                )
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

    stores.entities.source_entities = sort_entities(
        filter_entities_for_scope(
            sort_entities(source_entities), context.validation_scope
        )
    )
    stores.entities.source_non_matchable_entities = sort_entities(
        filter_entities_for_scope(
            sort_entities(source_non_matchable),
            context.validation_scope,
        )
    )
    stores.entities.source_index = build_entity_index(stores.entities.source_entities)
    stores.entities.source_by_id = {
        entity.canonical_id: entity for entity in stores.entities.source_entities
    }


def run_matching(
    context: ProjectContext,
    stores: ProjectStores,
) -> None:
    if not stores.entities.source_index or not stores.entities.target_index:
        logger.warning("Entity indexes not built; skipping matching.")
        return
    config = MatchingConfig.from_config(_require_config(context))
    results, by_source = execute_matching(
        stores.entities.source_index,
        stores.entities.target_index,
        config,
    )
    stores.matches.match_results = results
    stores.matches.match_by_source_id = by_source
    stores.matches.match_registry = dict(by_source)


def compile_rules(
    context: ProjectContext,
    stores: ProjectStores,
    add_validation_result: Callable[[Any], None],
) -> None:
    entity_rules: list[Any] = []
    compiler_evidence: list[Any] = []
    compiler_results: list[Any] = []

    if stores.entities.source_entities and stores.entities.source_index:
        entity_rules, compiler_evidence, compiler_results = compile_entity_rules(
            stores.entities.source_entities,
            _require_config(context),
        )

    stores.rules.rules = sorted(
        entity_rules,
        key=lambda rule: (rule.rule_id, rule.selector.source_entity_id),
    )
    stores.rules.rule_results = list(compiler_results)

    if compiler_results:
        rule_by_id = {rule.rule_id: rule for rule in stores.rules.rules}
        for result in compiler_results:
            rule = rule_by_id.get(result.rule_id)
            source_entity = stores.entities.source_by_id.get(result.source_entity_id)
            if rule is None or source_entity is None:
                continue
            add_validation_result(
                rule_result_to_validation(rule, result, source_entity, None)
            )

    if compiler_evidence:
        for evidence in compiler_evidence:
            if evidence.entity_id is None:
                continue
            source_entity = stores.entities.source_by_id.get(evidence.entity_id)
            if source_entity is None:
                continue
            add_validation_result(
                compiler_evidence_to_validation(evidence, source_entity)
            )


def evaluate_rules(
    context: ProjectContext,
    stores: ProjectStores,
    add_validation_result: Callable[[Any], None],
) -> None:
    if not (
        stores.rules.rules
        and stores.entities.source_index
        and stores.entities.target_index
    ):
        return

    from pythonarchtesting.core.evaluation import evaluate_rule
    from pythonarchtesting.core.models import EvalContext

    compiler_results = list(stores.rules.rule_results)
    ctx = EvalContext(
        source_index=stores.entities.source_index,
        target_index=stores.entities.target_index,
        matches=stores.matches.match_by_source_id,
        config=_require_config(context),
        source_by_id=stores.entities.source_by_id,
        target_by_id=stores.entities.target_by_id,
    )

    evaluated_results: list[Any] = []
    for rule in stores.rules.rules:
        if not rule.enabled:
            continue
        source_entity = stores.entities.source_by_id.get(rule.selector.source_entity_id)
        match = stores.matches.match_by_source_id.get(rule.selector.source_entity_id)
        if source_entity is None or match is None:
            continue
        target_entity = (
            stores.entities.target_by_id.get(match.target_id)
            if match.target_id
            else None
        )
        result = evaluate_rule(rule, source_entity, match, ctx)
        evaluated_results.append(result)
        add_validation_result(
            rule_result_to_validation(rule, result, source_entity, target_entity)
        )

    stores.rules.rule_results = compiler_results + evaluated_results


def analyze(
    context: ProjectContext,
    stores: ProjectStores,
    services: ProjectServices,
    add_validation_result: Callable[[Any], None],
) -> None:
    stores.reset_validation()
    stores.reset_analysis()
    stores.reset_evidence()
    build_entity_indexes(context, stores, services, add_validation_result)
    run_matching(context, stores)
    compile_rules(context, stores, add_validation_result)
    evaluate_rules(context, stores, add_validation_result)


def _syntax_validation(
    *,
    description: str,
    src_package: str,
    src_file: str,
    exc: SyntaxError,
) -> Any:
    from pythonarchtesting.state.validation import ValidationResult

    return ValidationResult(
        status=ValidationStatus.ERROR,
        description=description,
        check_type="extraction/syntax_error",
        src_function_name="",
        src_package=src_package,
        src_file=src_file,
        src_line_num=getattr(exc, "lineno", None),
        details={
            "exception": str(exc),
            "lineno": getattr(exc, "lineno", None),
            "offset": getattr(exc, "offset", None),
        },
    )
