"""JSON renderer."""

from __future__ import annotations

import json
from typing import Any, Dict


def render_json(report: Dict[str, Any]) -> str:
    """Render schema-v2 payload as deterministic JSON."""
    return json.dumps(report, indent=2, sort_keys=True)
