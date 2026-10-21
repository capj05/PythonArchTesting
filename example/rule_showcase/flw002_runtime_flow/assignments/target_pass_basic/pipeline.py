"""Runs the steps in the reference's order: parse, validate, enrich, store."""

from __future__ import annotations

from typing import Any

from . import steps


def import_record(line: str, sink: list[dict[str, Any]]) -> Any:
    record: Any = line
    record = steps.parse(record)
    record = steps.validate(record)
    record = steps.enrich(record)
    steps.store(record, sink)
    return record
