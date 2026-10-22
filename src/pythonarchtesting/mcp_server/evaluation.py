from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from pythonarchtesting.config import Config, load_config, resolve_projects_config
from pythonarchtesting.exceptions import ConfigurationError
from pythonarchtesting.mcp_server.errors import ToolInputError, require_absolute
from pythonarchtesting.mcp_server.reports import summarize_payload
from pythonarchtesting.report.lazy import generate_run_report
from pythonarchtesting.validation_scope import VALIDATION_SCOPES

CONFIG_FILENAME = ".pythonarchtesting"
DEFAULT_SANDBOX = "bwrap"
DEFAULT_SANDBOX_MEMORY_MB = 1024
_ALLOWED_SANDBOXES = ("limits", "bwrap")


def resolve_config(source: Path, config: Optional[str]) -> tuple[Config, str]:
    """Load the config for ``source`` and return it with the applied file path.

    Neither the working directory nor the environment is consulted, so the same
    call gives the same result whatever the MCP client's launch directory is.
    The second element is ``"defaults"`` when no config file applies.
    """
    config_path: Optional[Path] = None
    if config is not None:
        config_path = require_absolute(config, "config")
        if not config_path.is_file():
            raise ToolInputError(f"config does not exist: {config}")
    else:
        for directory in (source, source.parent):
            candidate = directory / CONFIG_FILENAME
            if candidate.is_file():
                config_path = candidate
                break
    loaded = load_config(
        config_path=str(config_path) if config_path else None,
        cli_args={"output_format": "json"},
        discover_from_cwd=False,
    )
    return loaded, str(config_path) if config_path else "defaults"


def _check_scope(validation_scope: str) -> None:
    if validation_scope not in VALIDATION_SCOPES:
        raise ToolInputError(
            f"validation_scope must be one of {', '.join(VALIDATION_SCOPES)}: "
            f"{validation_scope}"
        )


def validate_declarations_tool(
    source: str,
    reference_modules: Optional[list[str]] = None,
    validation_scope: str = "all",
    config: Optional[str] = None,
) -> dict[str, Any]:
    """Validate the marker declarations of ``source``; runs no target code."""
    from pythonarchtesting.declaration_validation import validate_declarations

    _check_scope(validation_scope)
    source_path = require_absolute(source, "source")
    try:
        loaded, applied = resolve_config(source_path, config)
        payload = validate_declarations(
            loaded, source_path, reference_modules or None, validation_scope
        )
    except (ConfigurationError, OSError) as exc:
        raise ToolInputError(str(exc)) from exc
    payload["config"] = applied
    return payload


def _sandbox_policy(dynamic: bool, sandbox: Optional[str], memory_mb: int) -> Any:
    """Build and check the sandbox for a dynamic run; None for static runs."""
    if not dynamic:
        if sandbox is not None or memory_mb != DEFAULT_SANDBOX_MEMORY_MB:
            raise ToolInputError(
                "sandbox and sandbox_memory_mb apply only with dynamic."
            )
        return None
    from pythonarchtesting.dynamic.sandbox import (
        SandboxPolicy,
        SandboxUnavailableError,
        check_available,
    )

    mode = sandbox or DEFAULT_SANDBOX
    if mode == "none":
        raise ToolInputError("the MCP server refuses an unconfined run: sandbox none")
    if mode not in _ALLOWED_SANDBOXES:
        raise ToolInputError(
            f"sandbox must be one of {', '.join(_ALLOWED_SANDBOXES)}: {mode}"
        )
    if memory_mb <= 0:
        raise ToolInputError("sandbox_memory_mb must be positive.")
    policy = SandboxPolicy(mode=mode, memory_mb=memory_mb)
    try:
        check_available(policy)
    except SandboxUnavailableError as exc:
        raise ToolInputError(f"sandbox {mode} is not available here: {exc}") from exc
    return policy


def _check_targets(
    targets: Optional[list[str]],
    targets_dir: Optional[str],
    project_pattern: Optional[str],
    exclude_patterns: Optional[list[str]],
) -> None:
    if bool(targets) == (targets_dir is not None):
        raise ToolInputError("give exactly one of targets and targets_dir")
    if targets_dir is None and (project_pattern or exclude_patterns):
        raise ToolInputError("project_pattern and exclude_patterns need targets_dir")


def run_evaluation(
    source: str,
    output_dir: str,
    targets: Optional[list[str]] = None,
    targets_dir: Optional[str] = None,
    project_pattern: Optional[str] = None,
    exclude_patterns: Optional[list[str]] = None,
    reference_modules: Optional[list[str]] = None,
    validation_scope: str = "all",
    dynamic: bool = False,
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> dict[str, Any]:
    """Evaluate targets against ``source`` and write JSON and Markdown reports."""
    from pythonarchtesting.runner import run_projects
    from pythonarchtesting.runner.skips import (
        count_runtime_results_unverified,
        count_runtime_rules_skipped,
    )

    _check_scope(validation_scope)
    source_path = require_absolute(source, "source")
    output_root = require_absolute(output_dir, "output_dir")
    for target in targets or []:
        require_absolute(target, "targets")
    if targets_dir is not None:
        require_absolute(targets_dir, "targets_dir")
    _check_targets(targets, targets_dir, project_pattern, exclude_patterns)
    policy = _sandbox_policy(dynamic, sandbox, sandbox_memory_mb)
    run_dir = output_root / datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S%fZ")
    try:
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
            sandbox=policy,
            on_target_done=on_progress,
        )
        report_json = run_dir / "report.json"
        report_markdown = run_dir / "markdown"
        rendered = generate_run_report(
            run_state, target_states, "json", loaded, report_json
        )
        generate_run_report(
            run_state, target_states, "markdown", loaded, report_markdown
        )
    except (ConfigurationError, OSError) as exc:
        raise ToolInputError(str(exc)) from exc
    result = summarize_payload(json.loads(rendered), str(report_json))
    result.update(
        {
            "config": applied,
            "run_dir": str(run_dir),
            "report_json": str(report_json),
            "report_markdown": str(report_markdown),
            "runtime_rules_skipped": count_runtime_rules_skipped(target_states),
            "runtime_results_unverified": count_runtime_results_unverified(
                target_states
            ),
        }
    )
    return result
