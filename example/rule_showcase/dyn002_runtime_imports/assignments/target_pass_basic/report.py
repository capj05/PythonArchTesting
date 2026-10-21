from __future__ import annotations

import json
from xml.sax.saxutils import escape


def render(rows: list[dict[str, str]]) -> str:
    return json.dumps(
        [{key: escape(value) for key, value in row.items()} for row in rows]
    )
