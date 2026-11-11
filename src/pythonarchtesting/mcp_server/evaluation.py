"""MCP tools that evaluate: ``run_evaluation`` writes the reports of a run,
``check_architecture`` checks one target in a loop, and
``validate_declarations_tool`` checks the reference's markers.

``resolve_config`` and ``sandbox_policy`` are the core's
(``runner.settings``) with its refusals as tool input errors; the other MCP
tools take the config and the sandbox through them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from pythonarchtesting.config import Config
from pythonarchtesting.exceptions import ConfigurationError
from pythonarchtesting.invalid_input import InvalidInputError
from pythonarchtesting.mcp_server.errors import ToolInputError, require_absolute
from pythonarchtesting.mcp_server.reports import summarize_payload
from pythonarchtesting.report.lazy import generate_run_report
from pythonarchtesting.runner import settings
from pythonarchtesting.runner.settings import DEFAULT_SANDBOX_MEMORY_MB
from pythonarchtesting.validation_scope import VALIDATION_SCOPES


def resolve_config(source: Path, config: Optional[str]) -> tuple[Config, str]:
    """Load the config for ``source`` and return it with the applied file path.

    Neither the working directory nor the environment is consulted, so the same
    call gives the same result whatever the MCP client's launch directory is.
    The second element is ``"defaults"`` when no config file applies.
    """
    try:
        return settings.resolve_config(source, config)
    except InvalidInputError as exc:
        raise ToolInputError(str(exc)) from exc


def sandbox_policy(dynamic: bool, sandbox: Optional[str], memory_mb: int) -> Any:
    """Build and check the sandbox for a dynamic run; None for static runs."""
    try:
        return settings.sandbox_policy(dynamic, sandbox, memory_mb)
    except InvalidInputError as exc:
        raise ToolInputError(str(exc)) from exc


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
    architecture: bool = False,
    mapping: Optional[dict[str, Any]] = None,
    *,
    states: Optional[list[Any]] = None,
) -> dict[str, Any]:
    """Evaluate targets against ``source`` and write JSON and Markdown reports
    (``runner.reported_run``). ``states``, when given, receives the run's
    target states (not a parameter of the MCP tool)."""
    from pythonarchtesting.runner.reported_run import run_and_report
    from pythonarchtesting.runner.skips import (
        count_results_undecided,
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
    policy = sandbox_policy(dynamic, sandbox, sandbox_memory_mb)
    mappings = None
    if mapping is not None:
        from pythonarchtesting.matching.assisted import mapping_from_data

        try:
            mappings = mapping_from_data(mapping)
        except ValueError as exc:
            raise ToolInputError(f"mapping: {exc}") from exc
    try:
        run = run_and_report(
            source_path,
            output_root,
            targets=targets,
            targets_dir=targets_dir,
            project_pattern=project_pattern,
            exclude_patterns=exclude_patterns,
            reference_modules=reference_modules,
            validation_scope=validation_scope,
            dynamic=dynamic,
            sandbox=policy,
            config=config,
            on_progress=on_progress,
            architecture=architecture,
            mappings=mappings,
        )
    except (ConfigurationError, OSError, InvalidInputError) as exc:
        raise ToolInputError(str(exc)) from exc
    if states is not None:
        states.extend(run.target_states)
    result = summarize_payload(json.loads(run.rendered), str(run.report_json))
    result.update(
        {
            "config": run.config,
            "run_dir": str(run.run_dir),
            "report_json": str(run.report_json),
            "report_markdown": str(run.report_markdown),
            "runtime_rules_skipped": count_runtime_rules_skipped(run.target_states),
            "runtime_results_unverified": count_runtime_results_unverified(
                run.target_states
            ),
            "results_undecided": count_results_undecided(run.target_states),
        }
    )
    return result


_CHECK_MODES = ("static", "full")
_CHECK_PROBLEMS_CAP = 20


def _mapping_outcome(found: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """The assisted pairs one target applied and refused, with the reasons."""
    applied: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    for match in found["matching"]["matches"]:
        for reason in match.get("reasons") or []:
            evidence = reason.get("evidence") or {}
            entry = {"pair": evidence.get("pair"), "source": match["source_entity_id"]}
            if reason.get("code") == "assisted_mapping":
                applied.append(entry)
            elif reason.get("code") == "assisted_mapping_rejected":
                refused.append({**entry, "reason": reason.get("message")})
    return {"applied": applied, "refused": refused}


def check_architecture(
    source: str,
    target: str,
    mode: str = "static",
    mapping: Optional[dict[str, Any]] = None,
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
) -> dict[str, Any]:
    """Check one target against the reference, for an agent fixing it in a loop.

    The same evaluation as the CLI, always with the reference as the model
    of the architecture (``--architecture``), and ``--dynamic`` in ``full``
    mode. Nothing is written: the verdict, the problems with their structured
    feedback and the changes nothing decided come back directly.
    """
    from pythonarchtesting.matching.assisted import mapping_from_data
    from pythonarchtesting.report.feedback import explain_result, is_problem
    from pythonarchtesting.runner import run_projects

    if mode not in _CHECK_MODES:
        raise ToolInputError(f"mode must be one of {', '.join(_CHECK_MODES)}: {mode}")
    source_path = require_absolute(source, "source")
    target_path = require_absolute(target, "target")
    dynamic = mode == "full"
    policy = sandbox_policy(dynamic, sandbox, sandbox_memory_mb)
    try:
        mappings = mapping_from_data(mapping) if mapping is not None else None
    except ValueError as exc:
        raise ToolInputError(f"mapping: {exc}") from exc
    try:
        loaded, applied = resolve_config(source_path, config)
        run_state, target_states = run_projects(
            config=loaded,
            source_path=str(source_path),
            targets=[str(target_path)],
            load_config_first=False,
            dynamic=dynamic,
            sandbox=policy,
            architecture=True,
            mappings=mappings,
        )
        rendered = generate_run_report(run_state, target_states, "json", loaded, None)
    except (ConfigurationError, OSError) as exc:
        raise ToolInputError(str(exc)) from exc
    report = json.loads(rendered)
    (found,) = report["targets"]
    # A marker of the reference that does not compile says nothing about the
    # target: it is the reference to fix, reported apart.
    broken = [
        r
        for r in found["results"]
        if "invalid_declaration" in str(r["rule_id"])
        or str(r["rule_id"]).startswith("compiler_")
    ]
    problems = [
        explain_result(r) for r in found["results"] if is_problem(r) and r not in broken
    ]
    undecided = sorted(
        {
            item
            for r in found["results"]
            if r["status"] == "OK"
            for item in (r.get("details") or {}).get("undecided") or []
        }
    )
    skipped = sum(1 for r in found["results"] if r["status"] == "SKIPPED")
    return {
        # The exit code counts the reference's broken markers too; nothing in
        # the target can fix them, so they do not keep it from passing.
        "passed": not problems if broken else found["exit_code"] == 0,
        # A pass holds only for what ran: a SKIPPED part (a runtime check in
        # static mode) did not look at the target.
        "complete": skipped == 0,
        "mode": mode,
        "config": applied,
        "reference_problems": [
            {
                "rule": r["rule_id"],
                "summary": str(
                    (r.get("details") or {}).get("compiler_reason")
                    or (r.get("details") or {}).get("summary")
                    or r.get("message")
                ),
            }
            for r in broken
        ],
        "problems_total": len(problems),
        "problems": problems[:_CHECK_PROBLEMS_CAP],
        "undecided": undecided,
        "skipped": skipped,
        "mapping": _mapping_outcome(found) if mappings else None,
        "unpaired": sum(
            1
            for r in found["results"]
            if (r.get("details") or {}).get("reason") == "required_target_missing"
        ),
    }


__all__ = [
    "DEFAULT_SANDBOX_MEMORY_MB",
    "check_architecture",
    "resolve_config",
    "run_evaluation",
    "sandbox_policy",
    "validate_declarations_tool",
]
