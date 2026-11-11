"""MCP tools of global mode: the taught principles checked in a free-form
project with no reference solution; the submission is its own reference.

1. ``discover_roles``: per principle, the entities that play its roles (found
   by code, ``global_mode.discovery``) and ``cases_needed``, the entities a
   check runs, each with what the catalogue asks of its cases.
2. ``prepare_global_task``: the discovery after the AI client's overrides,
   and the self-task of one principle written to ``out_dir`` with the cases
   the AI wrote (``task.toml``, ``selftask.json``, and ``discovery.json`` for
   the run). A polymorphism discovery with several bases (independent
   hierarchies) gives one task per base, in ``out_dir/<base>``.
3. ``run_global_evaluation``: each task judged (``global_mode.outcome``) and
   the outcomes summarised (``global_mode.summary``) into
   ``output_dir/global-report.json``.

Cases for an entity no check of the task runs (one of a role checked only
statically, a private function, a name the submission does not have) are
left out of the task and listed in ``ignored_cases`` with the reason, instead
of the core refusing the whole task. A submission with a file that does not
parse is ``unverified`` for every principle, the file and line named, and
nothing of it runs.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.entities import Entity
from pythonarchtesting.exceptions import ConfigurationError
from pythonarchtesting.global_mode.model import PrincipleOutcome, RoleDiscovery
from pythonarchtesting.global_mode.selftask import _runs_code
from pythonarchtesting.global_mode.source import Scan, scan
from pythonarchtesting.mcp_server.errors import ToolInputError, require_absolute
from pythonarchtesting.principles import Principle

DISCOVERY_FILENAME = "discovery.json"
REPORT_FILENAME = "global-report.json"
SYNTAX_ERROR = "syntax_error"


def _submission(path: str) -> Path:
    found = require_absolute(path, "submission")
    if not found.is_dir():
        raise ToolInputError(f"submission is not a directory: {path}")
    return found.resolve()


def _apart(path: str, name: str, sub: Path) -> Path:
    """``path`` (absolute), which must neither lie in the submission nor hold
    it: what the tools write there would become part of the project (a task
    of it, a copy of it inside itself)."""
    found = require_absolute(path, name).resolve()
    if found.is_relative_to(sub) or sub.is_relative_to(found):
        raise ToolInputError(
            f"{name} must lie outside the submission and not contain it: {path}"
        )
    return found


def _principle(principle: str) -> Principle:
    """The catalogue entry of a principle global mode can check."""
    from pythonarchtesting.global_mode.discovery import _REGISTRY
    from pythonarchtesting.mcp_server.principles import resolve_principle

    entry = resolve_principle(principle)
    if principle not in _REGISTRY:
        raise ToolInputError(
            f"principle {principle!r} has no role discovery yet; global mode "
            f"checks: {', '.join(sorted(_REGISTRY))}"
        )
    return entry


def _relative(file: str, submission: Path) -> str:
    path = Path(file)
    try:
        return path.resolve().relative_to(submission).as_posix()
    except ValueError:
        return path.as_posix()


def _scan(submission: Path) -> tuple[Scan, list[dict[str, Any]]]:
    """The submission as the core extracts it, read once per tool call
    (``global_mode.source``), and the files that do not parse (``file``
    relative to the submission, ``line``, ``why``): the core skips those, so
    their entities are missing."""
    try:
        scanned = scan(submission)
    except (ConfigurationError, OSError) as error:
        raise ToolInputError(str(error)) from error
    errors = [
        {
            "file": _relative(str(v.src_file), submission),
            "line": v.src_line_num,
            "why": str((v.details or {}).get("exception") or v.description),
        }
        for v in scanned.syntax_errors()
    ]
    return scanned, errors


def _covered(
    entry: Principle, discovery: RoleDiscovery, entities: Sequence[Entity]
) -> dict[str, tuple[str, Optional[Entity], Optional[str]]]:
    """Per name a check of the task runs: its role, its entity and, for a
    module with no public function, the problem. A module bound as a whole
    stands for its public functions (``task._resolve``)."""
    from pythonarchtesting.principles.task import _entity_name, _resolve

    covered: dict[str, tuple[str, Optional[Entity], Optional[str]]] = {}
    for role, bound in discovery.roles.items():
        if not _runs_code(entry, role):
            continue
        for b in bound:
            found, problem = _resolve(b.entity, entities)
            if not found:
                covered.setdefault(b.entity, (role, None, problem))
            for entity in found:
                covered.setdefault(_entity_name(entity), (role, entity, None))
    return covered


def _cases_needed(
    entry: Principle, discovery: RoleDiscovery, entities: Sequence[Entity]
) -> list[dict[str, Any]]:
    from pythonarchtesting.principles.catalog import STATIC_MARKERS

    texts = {
        role: "; ".join(
            str(c.cases)
            for c in entry.checks
            if c.role == role and c.marker not in STATIC_MARKERS and c.cases
        )
        for role in discovery.roles
    }
    needed: list[dict[str, Any]] = []
    for name, (role, entity, problem) in sorted(
        _covered(entry, discovery, entities).items()
    ):
        item: dict[str, Any] = {"entity": name, "role": role}
        if entity is not None:
            item["kind"] = entity.kind
            item["cases"] = texts[role]
        else:
            item["problem"] = problem
        needed.append(item)
    return needed


def discover_roles(
    submission: str, principles: list[str], assignment: Optional[str] = None
) -> dict[str, Any]:
    """Per principle its discovery (``RoleDiscovery.to_dict``) and the cases
    it needs (module docstring); ``assignment`` is returned as the AI
    client's context, never read."""
    from pythonarchtesting.global_mode.discovery import discover_roles as discover

    sub = _submission(submission)
    entries = [_principle(p) for p in principles]
    scanned, syntax = _scan(sub)
    entities = list(scanned.entities)
    found = []
    for entry in entries:
        discovery = discover(entry.id, entities)
        found.append(
            {
                **discovery.to_dict(),
                "cases_needed": (
                    []
                    if discovery.not_applied is not None
                    else _cases_needed(entry, discovery, entities)
                ),
            }
        )
    return {
        "submission": str(sub),
        "assignment": assignment,
        "syntax_errors": syntax,
        "principles": found,
    }


def _overrides(items: Optional[list[dict[str, Any]]]) -> dict[str, list[Any]]:
    """The overrides by role (``discovery.Override``), from the tool's list
    of ``{"entity", "action", "role", "why", "to_role"}``."""
    from pythonarchtesting.global_mode.discovery import Override

    by_role: dict[str, list[Any]] = {}
    for index, item in enumerate(items or []):
        if not isinstance(item, Mapping):
            raise ToolInputError(f"override {index} must be an object")
        missing = [
            key
            for key in ("entity", "action", "role", "why")
            if not isinstance(item.get(key), str)
        ]
        to_role = item.get("to_role")
        if missing or (to_role is not None and not isinstance(to_role, str)):
            raise ToolInputError(
                f"override {index} needs the strings entity, action (add, dispute "
                f"or move), role and why, and to_role for a move; missing: "
                f"{', '.join(missing) or 'to_role'}"
            )
        by_role.setdefault(item["role"], []).append(
            Override(item["entity"], item["action"], to_role, item["why"])
        )
    return by_role


def _checked_cases(cases: Any) -> dict[str, list]:
    """``cases`` as ``write_self_task`` takes them; a value TOML cannot hold
    (a JSON null) is an error naming the entity and the case."""
    from pythonarchtesting.global_mode.selftask import _toml

    if not isinstance(cases, Mapping):
        raise ToolInputError("cases must be an object: entity name -> list of cases")
    for name, items in cases.items():
        if not isinstance(items, list):
            raise ToolInputError(f"cases of {name!r} must be a list of cases")
        for index, case in enumerate(items):
            try:
                _toml(case)
            except TypeError as error:
                raise ToolInputError(
                    f"cases of {name!r}, case {index}: {error}; a case holds only "
                    "strings, numbers, booleans, lists and objects (no null)"
                ) from error
    return {str(name): list(items) for name, items in cases.items()}


def _ignored(
    name: str,
    entry: Principle,
    discovery: RoleDiscovery,
    entities: Sequence[Entity],
) -> str:
    """Why no check of the task runs ``name``."""
    from pythonarchtesting.principles.task import _entity_name

    for role, bound in discovery.roles.items():
        if any(b.entity == name for b in bound) and not _runs_code(entry, role):
            return f"bound to role {role!r}, whose checks read the code and run nothing"
    if not any(e.kind != "module" and _entity_name(e) == name for e in entities):
        return "the submission has no such function or method"
    return "no role of the principle binds it to a check that runs code"


def _base(part: RoleDiscovery) -> str:
    return part.roles["base"][0].entity


def _write_part(
    sub: Path,
    entry: Principle,
    part: RoleDiscovery,
    cases: Mapping[str, list],
    covered: Mapping[str, Any],
    task_dir: Path,
    scanned: Scan,
) -> dict[str, Any]:
    from pythonarchtesting.global_mode.outcome import _task_problems
    from pythonarchtesting.global_mode.selftask import write_self_task

    roles = {role: [b.entity for b in bound] for role, bound in part.roles.items()}
    task = write_self_task(
        sub,
        entry.id,
        roles,
        {name: c for name, c in cases.items() if name in covered},
        task_dir,
        entities=scanned.entities,
    )
    (task_dir / DISCOVERY_FILENAME).write_text(
        json.dumps(part.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "task_dir": str(task_dir),
        "roles": part.to_dict()["roles"],
        "conflicts": list(part.conflicts),
        "not_applied": part.not_applied,
        # A principle that does not apply runs nothing: nothing is dropped.
        "dropped": [] if part.not_applied else [dict(d) for d in task.dropped],
        "problems": (
            [] if part.not_applied else _task_problems(task_dir, None, scanned)
        ),
    }


def prepare_global_task(
    submission: str,
    principle: str,
    cases: dict[str, Any],
    out_dir: str,
    overrides: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Discover the roles of ``principle``, apply ``overrides`` and write its
    self-task(s) under ``out_dir`` (module docstring)."""
    from pythonarchtesting.global_mode.discovery import discover_roles as discover
    from pythonarchtesting.global_mode.discovery import split_by_base

    sub = _submission(submission)
    out = _apart(out_dir, "out_dir", sub)
    entry = _principle(principle)
    checked = _checked_cases(cases)
    by_role = _overrides(overrides)
    scanned, syntax = _scan(sub)
    entities = list(scanned.entities)
    discovery = discover(entry.id, entities, by_role)
    parts = split_by_base(discovery, entities)
    written = []
    used: set[str] = set()
    for part in parts:
        covered = {
            name: found
            for name, found in _covered(entry, part, entities).items()
            if found[1] is not None
        }
        used.update(covered)
        task_dir = out if len(parts) == 1 else out / _base(part)
        result = _write_part(sub, entry, part, checked, covered, task_dir, scanned)
        if len(parts) > 1:
            result["base"] = _base(part)
        written.append(result)
    summary: dict[str, Any] = {
        "principle": entry.id,
        "task_dirs": [w["task_dir"] for w in written],
        "ignored_cases": [
            {"entity": name, "reason": _ignored(name, entry, discovery, entities)}
            for name in checked
            if name not in used
        ],
        "syntax_errors": syntax,
    }
    summary["parts"] = written
    if len(written) == 1:
        summary.update(written[0])
    return summary


def _task(task_dir: str, sub: Path) -> tuple[Path, RoleDiscovery, Any]:
    from pythonarchtesting.global_mode.selftask import SELFTASK_FILENAME, SelfTask

    path = require_absolute(task_dir, "task_dirs")
    for name in (DISCOVERY_FILENAME, SELFTASK_FILENAME):
        if not (path / name).is_file():
            raise ToolInputError(
                f"{task_dir} has no {name}: prepare it with prepare_global_task"
            )
    discovery = RoleDiscovery.from_dict(
        json.loads((path / DISCOVERY_FILENAME).read_text(encoding="utf-8"))
    )
    prepared_for = json.loads((path / SELFTASK_FILENAME).read_text(encoding="utf-8"))[
        "submission"
    ]
    if Path(prepared_for) != sub:
        raise ToolInputError(
            f"{task_dir} was prepared for {prepared_for}, not for {sub}"
        )
    return path, discovery, SelfTask.load(path)


def _no_duplicates(tasks: Sequence[tuple[Path, RoleDiscovery, Any]]) -> None:
    """Each task once, and one task per principle (and base): a principle
    judged twice would be counted twice."""
    seen_dirs: set[Path] = set()
    seen: dict[tuple[str, Optional[str]], Path] = {}
    for path, discovery, _ in tasks:
        resolved = path.resolve()
        if resolved in seen_dirs:
            raise ToolInputError(f"task_dirs names {path} twice")
        seen_dirs.add(resolved)
        bases = discovery.roles.get("base") or ()
        key = (discovery.principle, bases[0].entity if len(bases) == 1 else None)
        if key in seen:
            what = discovery.principle + (f" (base {key[1]})" if key[1] else "")
            raise ToolInputError(
                f"task_dirs has two tasks of {what}: {seen[key]} and {path}"
            )
        seen[key] = path


def _unparsable(
    discovery: RoleDiscovery, syntax: Sequence[dict[str, Any]]
) -> PrincipleOutcome:
    """A principle of a submission with a file that does not parse: nothing
    of it ran, so nothing is verified, whatever the discovery found."""
    return PrincipleOutcome(
        principle=discovery.principle,
        status="unverified",
        roles=discovery.roles,
        findings=(),
        unverified=tuple({"reason": SYNTAX_ERROR, **error} for error in syntax),
        coverage=None,
        mutation=None,
        sites=0,
        violations=0,
    )


def run_global_evaluation(
    submission: str,
    task_dirs: list[str],
    output_dir: str,
    sandbox: Optional[str] = None,
) -> dict[str, Any]:
    """Judge every task of ``task_dirs`` on ``submission`` and write the
    summary to ``output_dir/global-report.json`` (module docstring); the runs
    write under ``output_dir/runs``."""
    from pythonarchtesting.global_mode.outcome import judge_principle
    from pythonarchtesting.global_mode.summary import summarize_outcomes

    sub = _submission(submission)
    out = _apart(output_dir, "output_dir", sub)
    if not task_dirs:
        raise ToolInputError(
            "task_dirs is empty: give the task_dirs of prepare_global_task"
        )
    tasks = [_task(task_dir, sub) for task_dir in task_dirs]
    _no_duplicates(tasks)
    scanned, syntax = _scan(sub)
    outcomes = []
    for index, (path, discovery, task) in enumerate(tasks):
        if syntax:
            outcomes.append(_unparsable(discovery, syntax))
            continue
        work_dir = out / "runs" / f"{index:02d}-{path.name}"
        try:
            outcomes.append(
                judge_principle(
                    sub, discovery, task, work_dir, sandbox=sandbox, scanned=scanned
                )
            )
        except (ConfigurationError, OSError) as error:
            raise ToolInputError(str(error)) from error
    summary = summarize_outcomes(outcomes)
    summary["submission"] = str(sub)
    out.mkdir(parents=True, exist_ok=True)
    report = out / REPORT_FILENAME
    report.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary["report_json"] = str(report)
    return summary


__all__ = [
    "DISCOVERY_FILENAME",
    "REPORT_FILENAME",
    "discover_roles",
    "prepare_global_task",
    "run_global_evaluation",
]
