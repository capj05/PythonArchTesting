"""Read a schema-v2 JSON report back."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pythonarchtesting.invalid_input import InvalidInputError
from pythonarchtesting.report.schema_v2 import validate_report_schema_v2


def read_report(path: Path) -> dict[str, Any]:
    """The report at ``path``, validated against schema v2; a file that is
    not JSON, or not such a report, raises ``InvalidInputError``."""
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise InvalidInputError(f"report is not valid JSON: {error}") from error
    errors = validate_report_schema_v2(report)
    if errors:
        raise InvalidInputError(f"report is not a schema v2 report: {errors[0]}")
    return report  # type: ignore[no-any-return]


__all__ = ["read_report"]
