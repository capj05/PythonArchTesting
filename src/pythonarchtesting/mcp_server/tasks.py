"""MCP tool ``prepare_task``: check a task an AI client wrote for a principle.

A task (``principles.task``) is ``task.toml`` next to an unannotated
reference: the principle, its roles bound to entities, and the cases of each
entity. ``prepare_task`` answers, deterministically, whether the task is ready
to grade a class:

1. ``task.toml`` is valid and fits the reference (``problems``); nothing else
   runs while it is not;
2. every generated check's cases run on the reference and cover it
   (``checks``, judged as ``check_cases`` judges them);
3. every typical error of the principle that names a mutation ``operator`` is
   caught: the operator seeds that kind of error into copies of the
   reference, in the entities of the check that detects it, and the check
   must fail on every copy and pass on the unchanged reference (``errors``).
   ``killed`` counts the mutants whose failure is classified as that error
   (its signature matched); a mutant the check catches as another error is
   ``killed_other``. An error is ``killed`` (accepted) only with at least one
   signature-matched kill; when every kill is another error's, its status is
   ``killed_other``.
   An error without an operator is ``not_verifiable_by_mutation``, a known gap
   is ``gap``; neither keeps the task from being accepted.

Nothing is written into the task: the mutants live in a temporary directory.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.exceptions import ConfigurationError
from pythonarchtesting.mcp_server.authoring import (
    DEFAULT_MAX_MUTANTS,
    DEFAULT_MIN_COVERAGE,
    _in_range,
    _judge,
    judge_cases,
)
from pythonarchtesting.mcp_server.errors import ToolInputError, require_absolute
from pythonarchtesting.mcp_server.evaluation import (
    DEFAULT_SANDBOX_MEMORY_MB,
    _sandbox_policy,
    resolve_config,
)

# The call ``add_io_call`` inserts for the callee an error's signature names.
_IO_MEMBERS = {"builtins:print": "print", "builtins:input": "input", "io:open": "open"}
_SURVIVORS_SHOWN = 3


def _problems(state: Any) -> list[str]:
    """What the compiler refused or warned about among the task's declarations
    (a ``compiler_invalid_param`` is a warning): each keeps the task from being
    accepted, so ``accepted: false`` always comes with its reason."""
    return [
        _problem(v)
        for v in state.compiler_validations
        if str(getattr(v.status, "value", v.status)).upper()
        in ("ERROR", "FAILED", "WARNING")
    ]


def _problem(validation: Any) -> str:
    """One compiler diagnostic: where, and why (the evidence's reason)."""
    details = validation.details or {}
    where = ".".join(
        str(part)
        for part in (validation.src_package, validation.src_function_name)
        if part
    )
    reasons = [
        " ".join(
            str(part)
            for part in (
                payload.get("decorator"),
                payload.get("param") and f"{payload['param']}:",
                payload.get("reason") or payload.get("issue"),
            )
            if part
        )
        for evidence in details.get("evidence") or []
        for payload in [evidence.get("payload") or {}]
    ]
    why = "; ".join(r for r in reasons if r) or details.get("summary") or ""
    head = f"{validation.check_type}" + (f" on {where}" if where else "")
    return f"{head}: {why or validation.description}"


def _bind(task_path: Path, loaded: Any) -> tuple[Any, list[Any], list[str]]:
    """The task, its checks and the problems that keep it from running."""
    from pythonarchtesting.principles.task import TaskError, bind_task, load_task
    from pythonarchtesting.runner.source_prep import prepare_source

    try:
        task = load_task(task_path)
        plain = prepare_source(config=loaded, source_path=task.reference)
        _, checks = bind_task(task, plain.source_entities)
        compiled = prepare_source(config=loaded, source_path=task_path)
    except TaskError as error:
        return None, [], error.problems
    return task, checks, _problems(compiled)


def _check_cases(
    task: Any,
    checks: list[Any],
    entities: dict[str, Any],
    min_coverage: float,
    policy: Any,
) -> list[dict[str, Any]]:
    judged: dict[str, dict[str, Any]] = {}
    report = []
    for check in checks:
        if check.entity not in judged:
            judged[check.entity] = judge_cases(
                task.reference,
                entities[check.entity_id],
                check.entity,
                list(check.params["cases"]),
                check.params["init"],
                min_coverage,
                5.0,
                policy,
            )
        found = judged[check.entity]
        report.append(
            {
                "role": check.role,
                "entity": check.entity,
                "marker": check.marker,
                "cases_ran": found["probe_status"] == "completed"
                and all(case["status"] != "error" for case in found["cases"]),
                "coverage": (found["coverage"] or {}).get("ratio"),
                "accepted": found["accepted"],
                "reasons": found["reasons"],
            }
        )
    return report


def _aimed(error: Any, checks: list[Any], entities: dict[str, Any]) -> set[Any]:
    """``(file, qualname)`` of the entities the check detecting ``error`` is on."""
    return {
        (str(entities[c.entity_id].filepath_rel), str(entities[c.entity_id].qualname))
        for c in checks
        if c.marker == error.detected_by
    }


def _mutants_for(
    error: Any, mutants: list[Any], aimed: set[Any]
) -> Optional[list[Any]]:
    """The mutants that seed ``error`` where its check looks; ``None`` when its
    signature names a callee the operator cannot call."""
    member = ""
    callee = error.signature.callee if error.signature else None
    if error.operator == "add_io_call" and callee is not None:
        if callee not in _IO_MEMBERS:
            return None
        member = _IO_MEMBERS[callee]
    return [
        m
        for m in mutants
        if m.operator == error.operator
        and (m.file, m.function) in aimed
        and (not member or m.member == member)
    ]


def _matched(principle: Any, error: Any, results: list[Any]) -> bool:
    """Whether a failed result of the mutant is classified as ``error``."""
    from pythonarchtesting.principles import choose_error, rule_marker

    return any(
        choose_error(principle, str(r.rule_id), fact) is error
        for r in results
        if r.status == "FAILED" and rule_marker(str(r.rule_id)) == error.detected_by
        for fact in (r.details or {}).get("facts") or []
    )


def _run_mutants(
    task: Any, loaded: Any, mutants: list[Any], markers: set[str], policy: Any
) -> tuple[list[Any], dict[str, list[Any]]]:
    """Results of the unchanged reference and of each mutant, for ``markers``."""
    from pythonarchtesting.principles import rule_marker
    from pythonarchtesting.runner import run_projects

    reference = Path(task.reference)
    ignore = shutil.ignore_patterns("__pycache__", ".*")
    with tempfile.TemporaryDirectory(prefix="pat-task-") as tmp:
        baseline = Path(tmp) / "reference" / reference.name
        shutil.copytree(reference, baseline, ignore=ignore)
        paths: dict[str, Path] = {}
        for mutant in mutants:
            copy = Path(tmp) / mutant.id / reference.name
            shutil.copytree(reference, copy, ignore=ignore)
            (copy / mutant.file).write_text(mutant.source, encoding="utf-8")
            for other, text in mutant.also:
                (copy / other).write_text(text, encoding="utf-8")
            paths[mutant.id] = copy
        _, states = run_projects(
            config=loaded,
            source_path=str(task.path),
            targets=[str(baseline), *(str(path) for path in paths.values())],
            load_config_first=False,
            dynamic=True,
            sandbox=policy,
            rule_filter=lambda rule: rule_marker(str(rule.rule_id)) in markers,
        )
        by_path = {Path(s.target_path).resolve(): list(s.rule_results) for s in states}
        return by_path[baseline.resolve()], {
            mutant_id: by_path[path.resolve()] for mutant_id, path in paths.items()
        }


def _error_entry(
    principle: Any, error: Any, chosen: Optional[list[Any]], results: dict
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "error": error.id,
        "detected_by": error.detected_by,
        "operator": error.operator,
    }
    if not chosen:
        entry["status"] = "no_mutants"
        entry["why"] = (
            f"{error.operator} found nothing to change in the entities "
            f"{error.detected_by} is on"
        )
        return entry
    outcomes = {m.id: _judge(results[m.id], str(error.detected_by))[0] for m in chosen}
    for m in chosen:
        # A kill counts for the error only when a failure is classified as it.
        if outcomes[m.id] == "killed" and not _matched(principle, error, results[m.id]):
            outcomes[m.id] = "killed_other"
    survivors = [m.description for m in chosen if outcomes[m.id] == "survived"]
    not_run = [m.description for m in chosen if outcomes[m.id] == "not_run"]
    killed = sum(1 for outcome in outcomes.values() if outcome == "killed")
    entry["status"] = (
        "survived"
        if survivors
        else "not_run" if not_run else "killed" if killed else "killed_other"
    )
    entry["mutants"] = len(chosen)
    entry["killed"] = killed
    entry["killed_other"] = sum(1 for o in outcomes.values() if o == "killed_other")
    entry["signature_matched"] = killed > 0
    if survivors or not_run:
        entry["survivors"] = (survivors + not_run)[:_SURVIVORS_SHOWN]
    if entry["status"] == "killed_other":
        entry["why"] = (
            f"{error.detected_by} fails on every mutant, but no failure is "
            f"classified as {error.id}: the mutants seed another error"
        )
    return entry


def _verify_errors(
    task: Any,
    loaded: Any,
    checks: list[Any],
    entities: dict[str, Any],
    max_mutants: int,
    policy: Any,
) -> dict[str, Any]:
    from pythonarchtesting.mutation.operators import generate_mutants

    principle = task.principle
    seeded = [e for e in principle.errors if e.operator and e.detected_by]
    operators = sorted({str(e.operator) for e in seeded})
    every = generate_mutants(Path(task.reference), operators) if operators else []
    chosen = {e.id: _mutants_for(e, every, _aimed(e, checks, entities)) for e in seeded}
    unique = {m.id: m for found in chosen.values() for m in found or []}
    truncated = len(unique) > max_mutants
    mutants = sorted(unique.values(), key=lambda m: m.id)[:max_mutants]
    kept = {m.id for m in mutants}
    markers = {str(e.detected_by) for e in seeded}
    base, results = (
        _run_mutants(task, loaded, mutants, markers, policy) if mutants else ([], {})
    )
    reference_passes = all(_judge(base, marker)[0] == "survived" for marker in markers)
    report = []
    for error in principle.errors:
        if error.gap is not None:
            report.append({"error": error.id, "status": "gap", "gap": error.gap})
        elif error.operator is None:
            report.append(
                {
                    "error": error.id,
                    "detected_by": error.detected_by,
                    "status": "not_verifiable_by_mutation",
                }
            )
        else:
            found = chosen[error.id]
            report.append(
                _error_entry(
                    principle,
                    error,
                    [m for m in found or [] if m.id in kept],
                    results,
                )
            )
    return {
        "reference_passes": reference_passes,
        "truncated": truncated,
        "errors": report,
    }


def prepare_task(
    task_dir: str,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
    max_mutants: int = DEFAULT_MAX_MUTANTS,
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
) -> dict[str, Any]:
    """Validate the task at ``task_dir``, run its cases and verify by mutation
    that its checks catch the principle's typical errors (module docstring)."""
    from pythonarchtesting.principles.task import is_task
    from pythonarchtesting.runner.source_prep import prepare_source

    task_path = require_absolute(task_dir, "task_dir")
    if not is_task(task_path):
        raise ToolInputError(f"no task.toml in {task_dir}")
    if not _in_range(min_coverage, 0.0, 1.0):
        raise ToolInputError("min_coverage must be a number in [0, 1]")
    if not _in_range(max_mutants, 1, 200) or int(max_mutants) != max_mutants:
        raise ToolInputError("max_mutants must be a whole number in [1, 200]")
    policy = _sandbox_policy(True, sandbox, sandbox_memory_mb)
    try:
        loaded, applied = resolve_config(task_path, config)
        task, checks, problems = _bind(task_path, loaded)
        result: dict[str, Any] = {
            "task_dir": str(task_path),
            "principle": task.principle.id if task is not None else None,
            "config": applied,
            "accepted": False,
            "problems": problems,
            "checks": [],
            "errors": [],
        }
        if task is None or problems:
            return result
        entities = {
            e.canonical_id: e
            for e in prepare_source(
                config=loaded, source_path=task.reference
            ).source_entities
        }
        result["checks"] = _check_cases(task, checks, entities, min_coverage, policy)
        result.update(
            _verify_errors(task, loaded, checks, entities, int(max_mutants), policy)
        )
    except (ConfigurationError, OSError) as exc:
        raise ToolInputError(str(exc)) from exc
    result["accepted"] = (
        all(check["accepted"] for check in result["checks"])
        and result["reference_passes"]
        and not result["truncated"]
        and all(
            e["status"] in ("killed", "not_verifiable_by_mutation", "gap")
            for e in result["errors"]
        )
    )
    return result


__all__ = ["prepare_task"]
