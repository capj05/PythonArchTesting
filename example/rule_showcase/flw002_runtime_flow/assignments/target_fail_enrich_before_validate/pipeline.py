"""Enriches the record before validating it: both steps run, in the wrong order.

``enrich`` needs a numeric age, so this target converts it first; it ends with
the same record as the reference. The order of the stages differs, so it
fails.
"""

from __future__ import annotations

from typing import Any

from . import steps


def import_record(line: str, sink: list[dict[str, Any]]) -> Any:
    record: Any = line
    record = steps.parse(record)
    record = steps.enrich({**record, "age": int(record["age"])})
    record = steps.validate({**record, "age": str(record["age"])})
    steps.store(record, sink)
    return record
