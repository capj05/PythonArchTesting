"""Runner implementation for source-once target-set execution."""

from __future__ import annotations

from typing import List, Optional, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.config.projects import ProjectsConfig, TargetSpec
from pythonarchtesting.evidence.collection import parse_python_modules
from pythonarchtesting.run_state import RunState, TargetRunState

from .orchestrator import run_projects as _run_projects_impl
from .source_prep import prepare_source
from .target_eval import evaluate_target as _evaluate_target_impl


def evaluate_target(
    *,
    run_state: RunState,
    spec: TargetSpec,
) -> TargetRunState:
    return _evaluate_target_impl(
        run_state=run_state,
        spec=spec,
        parse_python_modules_fn=parse_python_modules,
    )


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
) -> Tuple[RunState, List[TargetRunState]]:
    return _run_projects_impl(
        config=config,
        projects=projects,
        source_path=source_path,
        targets=targets,
        targets_dir=targets_dir,
        project_pattern=project_pattern,
        exclude_patterns=exclude_patterns,
        reference_modules=reference_modules,
        validation_scope=validation_scope,
        custom_config=custom_config,
        load_config_first=load_config_first,
        _evaluate_target_fn=evaluate_target,
    )


__all__ = ["prepare_source", "evaluate_target", "run_projects"]
