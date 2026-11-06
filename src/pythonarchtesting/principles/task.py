"""A task: a principle of the catalogue bound to an unannotated reference.

A task directory holds ``task.toml`` and the reference (``reference/`` by
default). ``task.toml`` names the principle, binds each of its roles to
entities of the reference and gives every bound entity its cases::

    principle = "io_separation"
    # reference = "reference"          # optional, relative to the task directory

    [roles]
    logic = ["grades"]                 # a module: its top-level public functions
    io = ["app.main"]                  # "mod.func", "mod.Class.method", "mod.Class"

    [cases]
    "grades.parse_grades" = [{ args = ["1 2 3 1"] }, { args = ["1 x 7"] }]
    "app.main" = [{ args = [], stdin = "1 2 3 1\\n" }]

    [init]                             # optional, per method: how to build self
    "mod.Class.method" = { args = [] }

Each ``[[checks]]`` of the catalogue entry becomes, for every entity bound to
its role, the declaration a marker ``marker(*modules, transitive=...,
cases=<the entity's cases>, init=<its init>)`` in that entity's body would
give. ``modules`` are the check's own plus, with ``target_role``, the modules
of the entities bound to that role. The declarations are produced by the same
parser that reads markers from source (``extract_annotation_declarations``)
and are compiled by the same compilers; the reference files are not touched.

Problems are collected and raised together as one ``TaskError``:

- a role a check needs (its ``role`` or ``target_role``) that ``[roles]``
  leaves unbound, a role the principle does not have, an empty role;
- an entity the reference does not have (with the closest names it has), a
  module without public functions;
- an entity of a check without ``cases``, cases or init for an entity no
  check covers; cases the compiler of the check's marker would refuse (an
  empty list, a case that is not a table, an unknown key) or holding
  ``nan``/``inf``;
- a reference that carries markers of its own: a task's reference must be
  unannotated, so that what is checked is what ``task.toml`` says.
"""

from __future__ import annotations

import ast
import dataclasses
import difflib
import math
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.entities import Entity
from pythonarchtesting.entities_extraction.annotations import (
    extract_annotation_declarations,
)
from pythonarchtesting.exceptions import ConfigurationError, ErrorContext
from pythonarchtesting.matching.models import NAME_REQUIRED
from pythonarchtesting.principles.catalog import (
    CheckTemplate,
    Principle,
    UnknownPrincipleError,
    get_principle,
)

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib

TASK_FILENAME = "task.toml"
DEFAULT_REFERENCE = "reference"
_KEYS = ("principle", "reference", "roles", "cases", "init")
_CLOSEST = 5  # reference entities an unknown name's message suggests


class TaskError(ConfigurationError):
    """``task.toml`` is malformed or does not fit its reference; ``problems``
    lists every problem found."""

    def __init__(self, path: Path, problems: Sequence[str]) -> None:
        self.problems = list(problems)
        super().__init__(
            f"{path}: " + "; ".join(self.problems),
            context=ErrorContext(file=str(path)),
            error_code="TASK_INVALID",
        )


@dataclass(frozen=True)
class Task:
    """A parsed ``task.toml``: entity names are as written there."""

    path: Path  # the task directory
    principle: Principle
    reference: Path
    roles: Mapping[str, tuple[str, ...]]
    cases: Mapping[str, list[Any]]
    init: Mapping[str, dict[str, Any]]


@dataclass(frozen=True)
class TaskCheck:
    """One declaration a task produces: a check of the catalogue on one entity."""

    role: str
    entity: str  # "module.qualname"
    entity_id: str
    marker: str
    params: Mapping[str, Any]


def is_task(path: Path) -> bool:
    """Whether ``path`` is a task directory (it holds ``task.toml``)."""
    return (Path(path) / TASK_FILENAME).is_file()


def needed_roles(principle: Principle) -> list[str]:
    """The roles a principle's checks refer to, in catalogue order."""
    found: list[str] = []
    for check in principle.checks:
        for role in (check.role, check.target_role):
            if role is not None and role not in found:
                found.append(role)
    return found


def _names(value: Any, where: str, problems: list[str]) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        problems.append(f"{where} must be a list of entity names")
        return ()
    if not value:
        problems.append(f"{where} binds no entity")
    return tuple(value)


def _per_entity(
    data: Mapping[str, Any], key: str, kind: type, problems: list[str]
) -> dict[str, Any]:
    table = data.get(key, {})
    if not isinstance(table, dict):
        problems.append(f"[{key}] must be a table keyed by entity name")
        return {}
    found: dict[str, Any] = {}
    for name, value in table.items():
        if not isinstance(value, kind):
            problems.append(
                f"[{key}] {name!r} must be "
                + ("a list of cases" if kind is list else "a table")
            )
            continue
        found[name] = value
    return found


def load_task(task_dir: Path) -> Task:
    """Parse and check ``task_dir/task.toml`` on its own (the reference's
    entities are checked by ``bind_task``)."""
    task_dir = Path(task_dir)
    path = task_dir / TASK_FILENAME
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise TaskError(path, [f"not valid TOML: {error}"]) from error
    problems: list[str] = [
        f"unknown key {key!r}; known: {', '.join(_KEYS)}"
        for key in data
        if key not in _KEYS
    ]
    principle_id = data.get("principle")
    if not isinstance(principle_id, str):
        raise TaskError(path, problems + ["'principle' must name a catalogue id"])
    try:
        principle = get_principle(principle_id)
    except UnknownPrincipleError as error:
        raise TaskError(path, problems + [str(error)]) from error
    reference_name = data.get("reference", DEFAULT_REFERENCE)
    reference = task_dir / str(reference_name)
    if not isinstance(reference_name, str) or not reference.is_dir():
        problems.append(f"the reference directory {str(reference)!r} does not exist")
    raw_roles = data.get("roles", {})
    roles: dict[str, tuple[str, ...]] = {}
    if not isinstance(raw_roles, dict):
        problems.append("[roles] must be a table: role = [entity, ...]")
        raw_roles = {}
    for role, value in raw_roles.items():
        if role not in principle.roles:
            problems.append(
                f"[roles] {role!r} is not a role of {principle.id!r} "
                f"(roles: {', '.join(principle.roles)})"
            )
            continue
        roles[role] = _names(value, f"[roles] {role!r}", problems)
    for role in needed_roles(principle):
        if role not in raw_roles:
            users = [
                check.marker
                for check in principle.checks
                if role in (check.role, check.target_role)
            ]
            problems.append(
                f"role {role!r} is not bound: the checks of {principle.id!r} need it "
                f"({', '.join(users)}); add {role} = [...] to [roles]"
            )
    cases = _per_entity(data, "cases", list, problems)
    init = _per_entity(data, "init", dict, problems)
    if problems:
        raise TaskError(path, problems)
    return Task(task_dir, principle, reference, roles, cases, init)


def _entity_name(entity: Entity) -> str:
    if entity.kind == "module":
        return str(entity.module_path)
    return f"{entity.module_path}.{entity.qualname}"


def _resolve(
    name: str, entities: Sequence[Entity]
) -> tuple[list[Entity], Optional[str]]:
    """The entities ``name`` stands for: a function, method or class by its
    dotted name, else a module's top-level public functions."""
    exact = [e for e in entities if e.kind != "module" and _entity_name(e) == name]
    if exact:
        return exact[:1], None
    if any(e.kind == "module" and e.module_path == name for e in entities):
        functions = [
            e
            for e in entities
            if e.kind == "function"
            and e.module_path == name
            and "." not in e.qualname
            and not e.qualname.startswith("_")
        ]
        if not functions:
            return [], f"module {name!r} has no top-level public function"
        return functions, None
    known = sorted({_entity_name(e) for e in entities if _entity_name(e)})
    closest = difflib.get_close_matches(name, known, n=_CLOSEST, cutoff=0.5)
    hint = f"; the closest: {', '.join(closest)}" if closest else ""
    return [], f"the reference has no {name!r}{hint}"


def _marker_text(marker: str, modules: Sequence[str], params: dict[str, Any]) -> str:
    arguments = [repr(module) for module in modules]
    arguments += [f"{key}={value!r}" for key, value in params.items()]
    return f"__archtest__: Annotated[None, {marker}({', '.join(arguments)})]\n"


def _declaration(
    check: CheckTemplate,
    modules: Sequence[str],
    entity: Entity,
    cases: list[Any],
    init: Optional[dict[str, Any]],
) -> Any:
    """The declaration a marker of ``check`` in ``entity``'s body would give."""
    params: dict[str, Any] = {}
    if check.transitive is not None:
        params["transitive"] = check.transitive
    params["cases"] = cases
    if init is not None:
        params["init"] = init
    text = _marker_text(check.marker, modules, params)
    (declaration,) = extract_annotation_declarations(ast.parse(text).body, text)
    return dataclasses.replace(declaration, lineno=entity.lineno, col=0)


def _plain(value: Any) -> bool:
    """Whether ``value`` is plain data a marker's literal could hold."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return True
    if isinstance(value, list):
        return all(_plain(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _plain(v) for k, v in value.items())
    return False


def _finite(value: Any) -> bool:
    """Whether no float in ``value`` is ``nan`` or ``inf`` (TOML allows them)."""
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_finite(item) for item in value)
    if isinstance(value, dict):
        return all(_finite(item) for item in value.values())
    return True


def _cases_problem(
    check: CheckTemplate, entity: Entity, cases: Any, init: Any
) -> Optional[str]:
    """What is wrong with an entity's cases and init, as the compiler of a
    marker would see them (the same validation), or ``None``."""
    from pythonarchtesting.rules.compilation.decorators.runtime_structure import (
        runtime_cases_problem,
    )

    if not _plain(cases) or (init is not None and not _plain(init)):
        return (
            "only strings, numbers, booleans, lists and tables (no dates) can be "
            "cases"
        )
    if not _finite(cases) or (init is not None and not _finite(init)):
        return "nan and inf are not case values"
    params: dict[str, Any] = {"cases": cases}
    if init is not None:
        params["init"] = init
    found = runtime_cases_problem(params, entity.kind, check.marker)
    if found is None:
        return None
    return (
        found[1]
        .replace("a non-empty list of dicts", "a non-empty list of tables")
        .replace("must be a dict", "must be a table")
    )


def bind_task(
    task: Task, entities: Sequence[Entity]
) -> tuple[list[Entity], list[TaskCheck]]:
    """The reference's ``entities`` with the task's declarations attached, and
    one ``TaskCheck`` per declaration. Raises ``TaskError`` with every problem."""
    path = task.path / TASK_FILENAME
    problems: list[str] = []
    annotated = sorted(
        {_entity_name(e) or "<root>" for e in entities if e.annotation_declarations}
    )
    if annotated:
        problems.append(
            "the reference carries markers of its own ("
            + ", ".join(annotated)
            + "); a task's reference must be unannotated: remove them, or "
            "evaluate the reference without task.toml"
        )
    bound: dict[str, list[Entity]] = {}
    for role, names in task.roles.items():
        bound[role] = []
        for name in names:
            found, problem = _resolve(name, entities)
            if problem is not None:
                problems.append(f"[roles] {role!r}: {problem}")
            bound[role].extend(e for e in found if e not in bound[role])
    covered: set[str] = set()
    declarations: dict[str, list[Any]] = {}
    checks: list[TaskCheck] = []
    for check in task.principle.checks:
        modules = list(check.modules)
        if check.target_role is not None:
            for entity in bound.get(check.target_role, []):
                if entity.module_path not in modules:
                    modules.append(str(entity.module_path))
        for entity in bound.get(check.role, []):
            name = _entity_name(entity)
            covered.add(name)
            cases = task.cases.get(name)
            if cases is None:
                problems.append(
                    f"[cases] {name!r} is missing: {check.marker} (role "
                    f"{check.role!r}) runs it; the cases must be: {check.cases}"
                )
                continue
            init = task.init.get(name)
            problem = _cases_problem(check, entity, cases, init)
            if problem is not None:
                problems.append(f"[cases] {name!r}: {problem}")
                continue
            declarations.setdefault(entity.canonical_id, []).append(
                _declaration(check, modules, entity, cases, init)
            )
            checks.append(
                TaskCheck(
                    role=check.role,
                    entity=name,
                    entity_id=entity.canonical_id,
                    marker=check.marker,
                    params={"modules": modules, "cases": cases, "init": init},
                )
            )
    for key, table in (("cases", task.cases), ("init", task.init)):
        for name in sorted(set(table) - covered):
            problems.append(f"[{key}] {name!r}: no check of the task covers it")
    if problems:
        # A problem of one entity's cases is found once per check on it.
        raise TaskError(path, list(dict.fromkeys(problems)))
    required = {e.canonical_id for found in bound.values() for e in found}
    return [
        _bound(e, declarations.get(e.canonical_id), e.canonical_id in required)
        for e in entities
    ], checks


def _bound(entity: Entity, declarations: Optional[list[Any]], required: bool) -> Entity:
    """``entity`` with the task's declarations and, when a role binds it, the
    flag that it is required by name (``NAME_REQUIRED``)."""
    changes: dict[str, Any] = {}
    if declarations is not None:
        changes["annotation_declarations"] = declarations
    if required:
        changes["extras"] = {**entity.extras, NAME_REQUIRED: True}
    return dataclasses.replace(entity, **changes) if changes else entity


__all__ = [
    "DEFAULT_REFERENCE",
    "TASK_FILENAME",
    "Task",
    "TaskCheck",
    "TaskError",
    "bind_task",
    "is_task",
    "load_task",
    "needed_roles",
]
