"""MCP tools that check what an LLM client proposes for a reference (F4).

The server never calls an LLM. A client proposes something (the cases that
drive a runtime check, a marker); these tools run it on the reference and say
deterministically whether it holds, so the client can iterate. The checks
themselves are the core's (``verification``); these tools check the
client's arguments and pass on what the core refuses as a tool input error.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.exceptions import ConfigurationError
from pythonarchtesting.invalid_input import InvalidInputError
from pythonarchtesting.mcp_server.errors import (
    ToolInputError,
    in_range,
    require_absolute,
)
from pythonarchtesting.mcp_server.evaluation import (
    DEFAULT_SANDBOX_MEMORY_MB,
    resolve_config,
    sandbox_policy,
)
from pythonarchtesting.verification.cases import DEFAULT_MIN_COVERAGE, judge_cases
from pythonarchtesting.verification.mutant_runs import DEFAULT_MAX_MUTANTS

_DETAILS = ("problems", "all")


def _reference_entities(source_path: Path, config: Optional[str]) -> list[Any]:
    from pythonarchtesting.runner.source_prep import prepare_source

    try:
        loaded, _ = resolve_config(source_path, config)
        state = prepare_source(config=loaded, source_path=source_path)
    except (ConfigurationError, OSError) as exc:
        raise ToolInputError(str(exc)) from exc
    return list(state.source_by_id.values())


def check_cases(
    source: str,
    entry: str,
    cases: list[dict[str, Any]],
    init: Optional[dict[str, Any]] = None,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
    timeout_s: float = 5.0,
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
) -> dict[str, Any]:
    """Run proposed ``cases`` of ``entry`` on the reference and judge them.

    The cases are accepted when every case could be set up and run (an
    exception the reference raises on purpose is fine and reported) and the
    lines of ``entry`` that the cases ran are at least ``min_coverage`` of
    all its lines. The calls between modules they drove are returned too:
    that is what a runtime check built on these cases will see.
    """
    from pythonarchtesting.rules.compilation.decorators.module_structure import (
        entry_problem,
    )

    source_path = require_absolute(source, "source")
    _not_a_task(source_path, "check_cases")
    if not in_range(min_coverage, 0.0, 1.0):
        raise ToolInputError("min_coverage must be a number in [0, 1]")
    params = {"entry": entry, "cases": cases, "init": init, "timeout_s": timeout_s}
    problem, entity = entry_problem(
        params, _reference_entities(source_path, config), "check_cases"
    )
    if problem is None and entity is None:
        problem = ("entry", "give the reference function as 'module.function'")
    if problem is not None:
        raise ToolInputError(f"{problem[0]}: {problem[1]}")
    assert entity is not None  # nosec B101 - narrowed by the checks above
    policy = sandbox_policy(True, sandbox, sandbox_memory_mb)
    return judge_cases(
        source_path, entity, entry, cases, init, min_coverage, timeout_s, policy
    )


def _not_a_task(source_path: Path, tool: str) -> None:
    from pythonarchtesting.principles.task import is_task

    if is_task(source_path):
        raise ToolInputError(
            f"source is a task directory (task.toml): give {tool} the reference "
            "directory itself, or check the whole task with prepare_task"
        )


def describe_architecture(
    source: str,
    mode: str = "static",
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
) -> dict[str, Any]:
    """The reference's architecture model (F4.1); see ``architecture.model``."""
    from pythonarchtesting.architecture.model import MODES, describe
    from pythonarchtesting.runner.source_prep import prepare_source

    # Resolved as the evaluation resolves it: the package name is its last part.
    source_path = require_absolute(source, "source").resolve()
    if mode not in MODES:
        raise ToolInputError(f"mode must be one of {', '.join(MODES)}: {mode}")
    policy = sandbox_policy(mode == "full", sandbox, sandbox_memory_mb)
    try:
        loaded, _ = resolve_config(source_path, config)
        state = prepare_source(config=loaded, source_path=source_path)
    except (ConfigurationError, OSError) as exc:
        raise ToolInputError(str(exc)) from exc
    return describe(state, mode=mode, source_root=source_path, sandbox=policy)


def verify_marker(
    source: str,
    rule: str,
    operators: Optional[list[str]] = None,
    files: Optional[list[str]] = None,
    libraries: Optional[list[str]] = None,
    max_mutants: int = DEFAULT_MAX_MUTANTS,
    dynamic: bool = False,
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
    detail: str = "problems",
) -> dict[str, Any]:
    """Check that the reference's ``rule`` catches seeded architectural violations.

    The named ``operators`` (all by default) seed violations into copies of
    the reference; each copy, and an unchanged one, is evaluated against the
    reference. ``rule`` is a marker name (``"forbid_imports"``) or a rule id
    prefix (``"DEP001"``). A mutant is *killed* when the rule fails on it
    with a violation, *survives* when it passes, and *did not run* when a
    runtime rule could not observe it. The marker is accepted when it passes
    on the unchanged reference and no mutant survives.

    Without ``operators`` only the operators the marker can see are used;
    without ``files`` only the files of the entities the marker is declared
    on (every file for a marker on the root package). Only the rules ``rule``
    names are evaluated. ``detail="problems"`` lists the survivors and the
    mutants that did not run (killed ones are counted per operator);
    ``detail="all"`` lists every mutant (``verification.marker``).
    """
    from pythonarchtesting.verification import marker

    source_path = require_absolute(source, "source")
    if not source_path.is_dir():
        raise ToolInputError(f"source does not exist: {source}")
    _not_a_task(source_path, "verify_marker")
    if not in_range(max_mutants, 1, 200) or int(max_mutants) != max_mutants:
        raise ToolInputError("max_mutants must be a whole number in [1, 200]")
    if detail not in _DETAILS:
        raise ToolInputError(f"detail must be one of {', '.join(_DETAILS)}: {detail}")
    try:
        result = marker.verify_marker(
            source_path,
            rule,
            operators,
            files,
            libraries,
            max_mutants,
            dynamic,
            sandbox,
            sandbox_memory_mb,
            config,
        )
    except InvalidInputError as exc:
        raise ToolInputError(str(exc)) from exc
    if detail != "all":
        result["mutants"] = [m for m in result["mutants"] if m["outcome"] != "killed"]
    return result


__all__ = [
    "DEFAULT_MAX_MUTANTS",
    "DEFAULT_MIN_COVERAGE",
    "check_cases",
    "describe_architecture",
    "verify_marker",
]
