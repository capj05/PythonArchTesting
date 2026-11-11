from __future__ import annotations

import difflib
from typing import Any, Optional

from pythonarchtesting.mcp_server.errors import ToolInputError, require_absolute
from pythonarchtesting.principles import (
    PLACEHOLDERS,
    SIGNATURE_KEYS,
    Principle,
    UnknownPrincipleError,
    get_principle,
    load_catalog,
)


def list_principles() -> list[dict[str, Any]]:
    """Every principle of the catalogue: id, name, level and its first sentence."""
    return [
        {
            "id": principle.id,
            "name": principle.name,
            "level": principle.level,
            "summary": principle.brief,
        }
        for _, principle in sorted(load_catalog().items())
    ]


def resolve_principle(principle_id: str) -> Principle:
    """The catalogue entry of ``principle_id``; an unknown id is a tool input
    error that suggests the closest known ids."""
    try:
        return get_principle(principle_id)
    except UnknownPrincipleError as error:
        close = difflib.get_close_matches(principle_id, error.known, n=3)
        hint = f"; did you mean: {', '.join(close)}" if close else ""
        raise ToolInputError(f"{error}{hint}") from error


def task_principle(source: str) -> Optional[str]:
    """The principle of the task at ``source``, or ``None`` when ``source`` is
    no task directory; a malformed ``task.toml`` is a tool input error."""
    from pythonarchtesting.principles.task import TaskError, is_task, load_task

    path = require_absolute(source, "source")
    if not is_task(path):
        return None
    try:
        return load_task(path).principle.id
    except TaskError as error:
        raise ToolInputError(str(error)) from error


def describe_principle(principle_id: str) -> dict[str, Any]:
    """The full catalogue entry of one principle, with the meaning of the
    placeholders of its errors' ``what`` and of the keys of their ``signature``."""
    entry = resolve_principle(principle_id).to_dict()
    entry["placeholders"] = dict(PLACEHOLDERS)
    entry["signature_keys"] = dict(SIGNATURE_KEYS)
    return entry
