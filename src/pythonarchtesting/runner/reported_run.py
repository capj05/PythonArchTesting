"""An evaluation run that writes its JSON and Markdown reports.

``run_and_report`` evaluates targets against a source and writes both reports
into a new, time-stamped run directory; the MCP tool ``run_evaluation`` and
global mode's ``judge_principle`` both run this way. A config or file problem
is raised as it is (``ConfigurationError``, ``OSError``); a config path that
cannot be used as ``InvalidInputError`` (``runner.settings``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.config import resolve_projects_config
from pythonarchtesting.report.lazy import generate_run_report
from pythonarchtesting.runner.settings import resolve_config


@dataclass(frozen=True)
class ReportedRun:
    """What a run wrote: the applied config (``"defaults"`` without a file),
    its directory, the JSON report as written (``rendered``) and its path,
    the Markdown report's directory, and the run's target states."""

    config: str
    run_dir: Path
    report_json: Path
    report_markdown: Path
    rendered: str
    target_states: list[Any]


def run_and_report(
    source_path: Path,
    output_root: Path,
    *,
    targets: Optional[list[str]] = None,
    targets_dir: Optional[str] = None,
    project_pattern: Optional[str] = None,
    exclude_patterns: Optional[list[str]] = None,
    reference_modules: Optional[list[str]] = None,
    validation_scope: str = "all",
    dynamic: bool = False,
    sandbox: Any = None,
    config: Optional[str] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    architecture: bool = False,
    mappings: Any = None,
) -> ReportedRun:
    """Evaluate the targets against ``source_path`` under the config
    ``resolve_config`` finds (or ``config``) and write the reports into
    ``output_root/run-<UTC time>``; ``sandbox`` is the policy of a dynamic
    run (``runner.settings.sandbox_policy``)."""
    from pythonarchtesting.runner import run_projects

    run_dir = output_root / datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S%fZ")
    loaded, applied = resolve_config(source_path, config)
    projects_cfg = resolve_projects_config(
        config=loaded,
        source_path=str(source_path),
        targets=targets or None,
        targets_dir=targets_dir,
        project_pattern=project_pattern,
        exclude_patterns=exclude_patterns or None,
        env_target_path=None,
    )
    run_dir.mkdir(parents=True, exist_ok=False)
    run_state, target_states = run_projects(
        config=loaded,
        projects=projects_cfg,
        source_path=str(source_path),
        targets=targets or None,
        targets_dir=targets_dir,
        reference_modules=reference_modules or None,
        project_pattern=project_pattern,
        exclude_patterns=exclude_patterns or None,
        validation_scope=validation_scope,
        load_config_first=False,
        dynamic=dynamic,
        sandbox=sandbox,
        architecture=architecture,
        mappings=mappings,
        on_target_done=on_progress,
    )
    report_json = run_dir / "report.json"
    report_markdown = run_dir / "markdown"
    rendered = generate_run_report(
        run_state, target_states, "json", loaded, report_json
    )
    generate_run_report(run_state, target_states, "markdown", loaded, report_markdown)
    return ReportedRun(
        config=applied,
        run_dir=run_dir,
        report_json=report_json,
        report_markdown=report_markdown,
        rendered=rendered,
        target_states=list(target_states),
    )


__all__ = ["ReportedRun", "run_and_report"]
