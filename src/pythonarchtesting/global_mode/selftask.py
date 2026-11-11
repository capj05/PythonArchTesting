"""A submission as its own reference: the task global mode checks it by.

``write_self_task`` writes ``task.toml`` (``principles.task``) whose
``reference`` is the absolute path of the submission itself, so the roles
bind the student's own entities and the existing core (``bind_task``,
``run_evaluation``, ``prepare_task``) checks the submission unchanged.

Entity names are the core's: relative to the submission root, the
directory given as ``submission`` (for a package, the package directory
itself). A module is ``actions`` (the package's ``__init__.py`` is ``""``),
a function ``actions.status``, a class ``ship.Cargo``, a method
``ship.Cargo.load``; ``$new`` in cases names ``ship.State``. Names are
written as given, never translated.

An entity a role binds whose checks run code (any check of the role whose
marker is not in ``catalog.STATIC_MARKERS``) but which has no cases is left
out of the task and listed in ``SelfTask.dropped``, so that it is reported
as unverified instead of being lost. A module bound as a whole stays bound
as a module when every one of its top-level public functions (as the core's
extraction and ``task._resolve`` see them, a ``def`` under a module-level
``if``/``try`` included) has cases;
otherwise it is replaced by the functions that have them, and the others
are dropped. A role left with no entity is not written: ``load_task`` then
reports the unbound role and the caller decides.

Beside ``task.toml``, ``selftask.json`` keeps the submission and the dropped
entities, so that a later run reads them back with ``SelfTask.load``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.entities import Entity
from pythonarchtesting.global_mode.source import source_entities as _source_entities
from pythonarchtesting.principles.catalog import (
    STATIC_MARKERS,
    Principle,
    get_principle,
)
from pythonarchtesting.principles.task import TASK_FILENAME, _entity_name, _resolve

SELFTASK_FILENAME = "selftask.json"
NO_CASES = "no cases"


@dataclass(frozen=True)
class SelfTask:
    """A written self-task: its directory and the entities left out of it
    (``{"entity", "role", "reason"}``)."""

    task_dir: Path
    dropped: tuple[dict[str, Any], ...]

    @classmethod
    def load(cls, task_dir: Path) -> SelfTask:
        """The self-task written to ``task_dir`` by ``write_self_task``."""
        task_dir = Path(task_dir)
        data = json.loads((task_dir / SELFTASK_FILENAME).read_text(encoding="utf-8"))
        return cls(task_dir, tuple(dict(d) for d in data["dropped"]))


def _string(text: str) -> str:
    # A JSON string is a TOML basic string, except that TOML also forbids a
    # literal DEL.
    return json.dumps(text, ensure_ascii=False).replace("\x7f", "\\u007f")


def _toml(value: Any) -> str:
    """``value`` as a TOML value on one line (tables inline)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        return repr(value) if math.isfinite(value) else ("inf" if value > 0 else "-inf")
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, Mapping):
        items = ", ".join(f"{_string(str(k))} = {_toml(v)}" for k, v in value.items())
        return "{ " + items + " }" if items else "{}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml(v) for v in value) + "]"
    raise TypeError(f"cannot write {type(value).__name__} {value!r} as TOML")


def _table(name: str, entries: Mapping[str, Any]) -> list[str]:
    if not entries:
        return []
    return ["", f"[{name}]"] + [
        f"{_string(k)} = {_toml(v)}" for k, v in entries.items()
    ]


def _runs_code(principle: Principle, role: str) -> bool:
    """Whether a check of ``role`` runs the entities it covers."""
    return any(
        check.role == role and check.marker not in STATIC_MARKERS
        for check in principle.checks
    )


def _kept(
    entities: Sequence[Entity],
    role: str,
    names: Sequence[str],
    cases: Mapping[str, list],
) -> tuple[list[str], list[dict[str, Any]]]:
    """The names of a role that keep their binding, and the dropped ones. A
    name stands for what ``task._resolve`` makes of it, so a module's
    functions are exactly the ones ``bind_task`` will ask cases for."""
    kept: list[str] = []
    dropped: list[dict[str, Any]] = []
    for name in names:
        if name in cases:
            kept.append(name)
            continue
        found, _ = _resolve(name, entities)
        is_module = any(e.kind == "module" and e.module_path == name for e in entities)
        if not is_module or not found:
            # An entity without cases is dropped; a module without public
            # functions is left for the core to report.
            if is_module:
                kept.append(name)
            else:
                dropped.append({"entity": name, "role": role, "reason": NO_CASES})
            continue
        qualified = [_entity_name(e) for e in found]
        with_cases = [q for q in qualified if q in cases]
        if len(with_cases) == len(qualified):
            kept.append(name)
            continue
        kept.extend(with_cases)
        dropped.extend(
            {"entity": q, "role": role, "reason": NO_CASES}
            for q in qualified
            if q not in cases
        )
    return list(dict.fromkeys(kept)), dropped


def write_self_task(
    submission: Path,
    principle: str,
    roles: Mapping[str, Sequence[str]],
    cases: Mapping[str, list],
    out_dir: Path,
    init: Mapping[str, dict] | None = None,
    *,
    entities: Optional[Sequence[Entity]] = None,
) -> SelfTask:
    """Write the task of ``principle`` over ``submission`` to ``out_dir``
    (module docstring). Raises ``UnknownPrincipleError`` for an unknown
    principle; every other problem of the task is ``load_task``'s to report.
    ``entities`` are the submission's (``source.source_entities``), read
    when needed and not given."""
    catalogue_entry = get_principle(principle)
    submission = Path(submission).resolve()
    out_dir = Path(out_dir)
    bound: dict[str, list[str]] = {}
    dropped: list[dict[str, Any]] = []
    for role, names in roles.items():
        if _runs_code(catalogue_entry, role):
            if entities is None and any(name not in cases for name in names):
                entities = _source_entities(submission)
            kept, lost = _kept(entities or [], role, names, cases)
            dropped.extend(lost)
        else:
            kept = list(names)
        if kept:
            bound[role] = kept
    lines = [
        f"principle = {_toml(principle)}",
        f"reference = {_toml(str(submission))}",
        *_table("roles", bound),
        *_table("cases", cases),
        *_table("init", init or {}),
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / TASK_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / SELFTASK_FILENAME).write_text(
        json.dumps(
            {"submission": str(submission), "dropped": dropped},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return SelfTask(out_dir, tuple(dropped))


__all__ = ["NO_CASES", "SELFTASK_FILENAME", "SelfTask", "write_self_task"]
