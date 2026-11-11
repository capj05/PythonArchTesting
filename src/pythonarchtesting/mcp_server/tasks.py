"""MCP tool ``prepare_task``: check a task an AI client wrote for a principle.

A task (``principles.task``) is ``task.toml`` next to an unannotated
reference: the principle, its roles bound to entities, and the cases of each
entity. ``prepare_task`` answers, deterministically, whether the task is ready
to grade a class: its declarations are valid, its cases run and cover the
reference, and its checks catch the principle's typical errors seeded by
mutation. The verification is the core's (``principles.task_verification``,
whose docstring gives every status); this tool checks the client's
arguments and passes on what the core refuses as a tool input error.

Nothing is written into the task: the mutants live in a temporary directory.
"""

from __future__ import annotations

from typing import Any, Optional

from pythonarchtesting.exceptions import ConfigurationError
from pythonarchtesting.invalid_input import InvalidInputError
from pythonarchtesting.mcp_server.authoring import (
    DEFAULT_MAX_MUTANTS,
    DEFAULT_MIN_COVERAGE,
)
from pythonarchtesting.mcp_server.errors import (
    ToolInputError,
    in_range,
    require_absolute,
)
from pythonarchtesting.mcp_server.evaluation import (
    DEFAULT_SANDBOX_MEMORY_MB,
    sandbox_policy,
)
from pythonarchtesting.principles.task_verification import verify_task


def prepare_task(
    task_dir: str,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
    max_mutants: int = DEFAULT_MAX_MUTANTS,
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
    *,
    scanned: Any = None,
    baseline: Optional[list[Any]] = None,
) -> dict[str, Any]:
    """Validate the task at ``task_dir``, run its cases and verify by mutation
    that its checks catch the principle's typical errors (module docstring).

    ``scanned`` and ``baseline`` (neither is a parameter of the MCP tool) are
    what a caller already has: the reference's entities
    (``runner.source_prep.Scan``) and the results of the unchanged reference
    run by the task's checks (``verify_task``)."""
    from pythonarchtesting.principles.task import is_task

    task_path = require_absolute(task_dir, "task_dir")
    if not is_task(task_path):
        raise ToolInputError(f"no task.toml in {task_dir}")
    if not in_range(min_coverage, 0.0, 1.0):
        raise ToolInputError("min_coverage must be a number in [0, 1]")
    if not in_range(max_mutants, 1, 200) or int(max_mutants) != max_mutants:
        raise ToolInputError("max_mutants must be a whole number in [1, 200]")
    policy = sandbox_policy(True, sandbox, sandbox_memory_mb)
    try:
        return verify_task(
            task_path,
            config,
            policy,
            min_coverage,
            int(max_mutants),
            scanned=scanned,
            baseline=baseline,
        )
    except (ConfigurationError, OSError, InvalidInputError) as exc:
        raise ToolInputError(str(exc)) from exc


__all__ = ["prepare_task"]
