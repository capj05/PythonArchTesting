"""Runner orchestration for source-once target-set execution."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.config.projects import (
    ProjectsConfig,
    TargetSpec,
    resolve_projects_config,
)
from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.infrastructure.logging import get_logger
from pythonarchtesting.run_state import RunState, TargetRunState
from pythonarchtesting.state import ValidationResult, ValidationStatus

from .source_prep import _framework_version, prepare_source
from .target_eval import evaluate_target

# Get logger for this module.
logger = get_logger(__name__)


def _build_empty_run_state(
    *,
    config: Config,
    source_path: Path,
    validation_scope: str,
) -> RunState:
    empty_index = build_entity_index([])
    return RunState(
        config=config,
        source_path=source_path,
        reference_modules=[],
        source_entities=[],
        source_index=empty_index,
        source_by_id={},
        rules=[],
        compiler_results=[],
        compiler_validations=[],
        run_generated_at=datetime.now(timezone.utc),
        framework_version=_framework_version(),
        validation_scope=validation_scope,
    )


def _evaluate_target_safe(
    *,
    run_state: RunState,
    spec: TargetSpec,
    evaluate_target_fn: Callable[..., TargetRunState],
) -> TargetRunState:
    try:
        target_state = evaluate_target_fn(run_state=run_state, spec=spec)
    except Exception as exc:
        logger.exception("Target failed: id=%s path=%s", spec.target_id, spec.path)
        error_result = ValidationResult(
            status=ValidationStatus.ERROR,
            description="Target evaluation failed.",
            check_type="runner/target_error",
            src_function_name="",
            project_name=spec.target_id,
            details={
                "error": str(exc),
                "type": type(exc).__name__,
            },
        )
        empty_index = build_entity_index([])
        target_state = TargetRunState(
            target_id=spec.target_id,
            target_path=spec.path,
            target_entities=[],
            target_index=empty_index,
            target_by_id={},
            match_results=[],
            match_by_source={},
            rule_results=[],
            validation_results=[error_result],
        )
    return target_state


def run_projects(
    config: Optional[Config] = None,
    projects: Optional[ProjectsConfig] = None,
    *,
    source_path: Optional[str] = None,
    targets: Optional[List[str]] = None,
    targets_dir: Optional[str] = None,
    project_pattern: Optional[str] = None,
    exclude_patterns: Optional[List[str]] = None,
    reference_modules: Optional[List[str]] = None,
    validation_scope: str = "all",
    custom_config: Optional[str] = None,
    load_config_first: bool = True,
    _prepare_source_fn: Callable[..., RunState] = prepare_source,
    _evaluate_target_fn: Callable[..., TargetRunState] = evaluate_target,
) -> Tuple[RunState, List[TargetRunState]]:
    if load_config_first and config is None:
        from pythonarchtesting.config import load_config

        config = load_config(config_path=custom_config, cli_args={})

    if config is None:
        raise ValueError("Config is required for run_projects")

    projects_cfg = projects or resolve_projects_config(
        config,
        source_path=source_path,
        targets=targets,
        targets_dir=targets_dir,
        project_pattern=project_pattern,
        exclude_patterns=exclude_patterns,
        env_target_path=os.environ.get("PYTHON_ARCH_TARGET_PATH"),
    )

    run_state = _prepare_source_fn(
        config=config,
        source_path=projects_cfg.source_path,
        reference_modules=reference_modules,
        validation_scope=validation_scope,
    )

    logger.info(
        "Run started: source_path=%s targets=%d",
        run_state.source_path,
        len(projects_cfg.targets),
    )

    target_states: List[TargetRunState] = []
    for spec in projects_cfg.targets:
        logger.info("Target start: id=%s path=%s", spec.target_id, spec.path)
        target_state = _evaluate_target_safe(
            run_state=run_state,
            spec=spec,
            evaluate_target_fn=_evaluate_target_fn,
        )
        logger.info(
            "Target done: id=%s path=%s entities=%d matches=%d "
            "rule_results=%d validation_results=%d",
            spec.target_id,
            spec.path,
            len(target_state.target_entities),
            len(target_state.match_results),
            len(target_state.rule_results),
            len(target_state.validation_results),
        )
        target_states.append(target_state)

    return run_state, target_states
