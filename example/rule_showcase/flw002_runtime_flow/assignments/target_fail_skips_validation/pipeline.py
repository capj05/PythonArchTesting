"""Stores records without validating them: the validated stage never runs."""

from __future__ import annotations

from typing import Any

from . import steps


def import_record(line: str, sink: list[dict[str, Any]]) -> Any:
    record: Any = line
    record = steps.parse(record)
    record = steps.enrich({**record, "age": int(record["age"] or 0)})
    steps.store(record, sink)
    return record
