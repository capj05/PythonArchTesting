"""JSON renderer."""

from __future__ import annotations

import json

from ..ir.models import ReportDocument
from ..ir.serialize import to_legacy_schema_v2


def render_json(document: ReportDocument) -> str:
    """Render typed report document as deterministic schema-v2 JSON."""
    return json.dumps(to_legacy_schema_v2(document), indent=2, sort_keys=True)
