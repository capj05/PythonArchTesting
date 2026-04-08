"""
Multi-target runner target evaluation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Tuple

from pythonarchtesting.config.accessors import get_bool
from pythonarchtesting.config.projects import TargetSpec
from pythonarchtesting.core.evaluation import evaluate_rules_for_target
from pythonarchtesting.entities import Entity, build_entity_index, sort_entities
from pythonarchtesting.entities_extraction import (
    extract_entities_from_ast_with_nonmatchable,
)
from pythonarchtesting.evidence.collection import (
    ParsedModule,
    parse_python_modules,
)
from pythonarchtesting.matching import MatchingConfig, run_matching
from pythonarchtesting.state import ValidationResult, ValidationStatus
from pythonarchtesting.state.validation import rule_result_to_validation
from pythonarchtesting.state_multi import RunState, TargetRunState
from pythonarchtesting.validation_scope import filter_entities_for_scope

ParsePythonModulesFn = Callable[
    ...,
    Tuple[List[ParsedModule], List[Tuple[Path, SyntaxError]]],
]


def evaluate_target(
    *,
    run_state: RunState,
    spec: TargetSpec,
    parse_python_modules_fn: ParsePythonModulesFn = parse_python_modules,
) -> TargetRunState:
    config = run_state.config
    include_nested = get_bool(config, "matching", "include_nested_functions", False)

    target_entities: List[Entity] = []
    validation_results: List[ValidationResult] = []
    parsed_modules, parse_errors = parse_python_modules_fn(
        root_path=spec.path,
        config=config,
        target_module_name=None,
    )
    for file_path, exc in parse_errors:
        validation_results.append(
            ValidationResult(
                status=ValidationStatus.ERROR,
                description="Syntax error during target entity extraction.",
                check_type="extraction/syntax_error",
                src_function_name="",
                src_package=str(spec.path),
                src_file=str(file_path),
                src_line_num=getattr(exc, "lineno", None),
                project_name=spec.target_id,
                details={
                    "exception": str(exc),
                    "lineno": getattr(exc, "lineno", None),
                    "offset": getattr(exc, "offset", None),
                },
            )
        )

    for parsed in parsed_modules:
        matchable, _ = extract_entities_from_ast_with_nonmatchable(
            parsed.tree,
            parsed.file_text,
            parsed.file_path,
            spec.path,
            None,
            role="target",
            include_nested_functions=include_nested,
            root_label=spec.target_id,
        )
        target_entities.extend(matchable)

    target_entities = sort_entities(target_entities)
    target_entities = sort_entities(
        filter_entities_for_scope(target_entities, run_state.validation_scope)
    )
    target_index = build_entity_index(target_entities)
    target_by_id = {e.canonical_id: e for e in target_entities}

    matching_cfg = MatchingConfig.from_config(config)
    match_results, match_by_source = run_matching(
        run_state.source_index, target_index, matching_cfg
    )

    rule_results = list(run_state.compiler_results)
    validation_results.extend(run_state.compiler_validations)

    eval_rule_results, _ = evaluate_rules_for_target(
        rules=run_state.rules,
        source_index=run_state.source_index,
        target_index=target_index,
        matches=match_by_source,
        config=config,
        source_by_id=run_state.source_by_id,
        target_by_id=target_by_id,
    )
    rule_results.extend(eval_rule_results)
    rule_by_id = {rule.rule_id: rule for rule in run_state.rules}
    for result in eval_rule_results:
        rule = rule_by_id.get(result.rule_id)
        source_entity = run_state.source_by_id.get(result.source_entity_id)
        target_entity = (
            target_by_id.get(result.target_entity_id)
            if result.target_entity_id
            else None
        )
        if rule is None or source_entity is None:
            continue
        validation_results.append(
            rule_result_to_validation(rule, result, source_entity, target_entity)
        )

    return TargetRunState(
        target_id=spec.target_id,
        target_path=spec.path,
        target_entities=target_entities,
        target_index=target_index,
        target_by_id=target_by_id,
        match_results=match_results,
        match_by_source=match_by_source,
        rule_results=rule_results,
        validation_results=validation_results,
    )
