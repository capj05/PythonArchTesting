"""Runner target evaluation."""

from __future__ import annotations

import ast
from dataclasses import replace
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
from pythonarchtesting.run_state import RunState, TargetRunState
from pythonarchtesting.state import ValidationResult, ValidationStatus
from pythonarchtesting.state.validation import rule_result_to_validation
from pythonarchtesting.validation_scope import filter_entities_for_scope

ParsePythonModulesFn = Callable[
    ...,
    Tuple[List[ParsedModule], List[Tuple[Path, SyntaxError]]],
]


def _relative_file(file_path: Path, root: Path) -> str:
    try:
        return Path(file_path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(file_path).name


def _left_out_root_init(source_path: Path, target_path: Path) -> bool:
    """Whether the target is a package whose ``__init__.py`` was left out: the
    reference's root is a package, the target's root has Python files but no
    ``__init__.py``. Its root module is then an empty one, so the reference's
    root module has its counterpart, as with an empty ``__init__.py``."""
    if not (Path(source_path) / "__init__.py").is_file():
        return False
    if (target_path / "__init__.py").exists() or (
        target_path / "__init__.pyi"
    ).exists():
        return False
    return target_path.is_dir() and any(target_path.glob("*.py"))


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
                    "message": getattr(exc, "msg", None) or str(exc),
                    # Relative to the target's root: the submission's file,
                    # unlike a reference's syntax error every target repeats.
                    "file": _relative_file(file_path, Path(spec.path)),
                    "lineno": getattr(exc, "lineno", None),
                    "offset": getattr(exc, "offset", None),
                },
            )
        )

    modules = [
        (parsed.tree, parsed.file_text, parsed.file_path) for parsed in parsed_modules
    ]
    if _left_out_root_init(run_state.source_path, Path(spec.path)):
        # Evaluated as if the beginner's missing __init__.py were there, empty.
        modules.append((ast.parse(""), "", Path(spec.path) / "__init__.py"))
    for tree, file_text, file_path in modules:
        matchable, _ = extract_entities_from_ast_with_nonmatchable(
            tree,
            file_text,
            file_path,
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
    # Scores first, then the teacher's mapping, then pairing by name: a pair
    # made by name never stands in the way of an explicit one.
    match_results, match_by_source = run_matching(
        run_state.source_index,
        target_index,
        replace(matching_cfg, name_fallback=False),
    )
    # A target's own pairs add to the common ones, and win over them.
    pairs = {
        **run_state.mappings.get("*", {}),
        **run_state.mappings.get(spec.target_id, {}),
    }
    if pairs:
        from pythonarchtesting.matching.assisted import apply_mapping

        match_results, match_by_source = apply_mapping(
            match_results, match_by_source, run_state.source_index, target_index, pairs
        )
    if matching_cfg.name_fallback:
        from pythonarchtesting.matching.fallback import pair_by_name

        match_results, match_by_source = pair_by_name(
            match_results, match_by_source, run_state.source_index, target_index
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
        target_root=spec.path if run_state.dynamic_enabled else None,
        source_root=run_state.source_path if run_state.dynamic_enabled else None,
        sandbox=run_state.sandbox,
        reference_runs=run_state.reference_runs,
        target_package=Path(spec.path).name,
        source_package=Path(run_state.source_path).name,
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
