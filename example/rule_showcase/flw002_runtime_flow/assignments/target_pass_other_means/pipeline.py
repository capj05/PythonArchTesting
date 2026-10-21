"""Reaches parse and validate through a helper, and computes other values.

``_prepare`` wraps the first two steps, the variable has another name, and
the steps' results differ from the reference's (see ``steps.py``). The steps
still run in the reference's order, so the target passes.
"""

from __future__ import annotations

from typing import Any

from . import steps


def _prepare(line: str) -> dict[str, Any]:
    return steps.validate(steps.parse(line))


def import_record(line: str, sink: list[dict[str, Any]]) -> Any:
    entry = steps.enrich(_prepare(line))
    steps.store(entry, sink)
    return entry
