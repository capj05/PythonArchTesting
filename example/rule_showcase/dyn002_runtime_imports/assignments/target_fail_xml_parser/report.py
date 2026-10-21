"""Imports ``xml.dom.minidom``: under the forbidden ``xml``, outside the allow-list.

Only ``xml.sax.saxutils`` is allowed, so this fails although the reference
itself imports from ``xml``.
"""

from __future__ import annotations

import json
from xml.dom import minidom
from xml.sax.saxutils import escape


def render(rows: list[dict[str, str]]) -> str:
    _ = minidom
    return json.dumps(
        [{key: escape(value) for key, value in row.items()} for row in rows]
    )
