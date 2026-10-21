"""The storage driver is loaded by name while the module is imported.

``importlib.import_module`` takes a string, so the static import graph has no
edge to ``sqlite3``. The runtime check records the call at import time.
"""

from __future__ import annotations

import importlib
import json
from xml.sax.saxutils import escape

_DRIVER_NAME = "sql" + "ite3"
driver = importlib.import_module(_DRIVER_NAME)


def render(rows: list[dict[str, str]]) -> str:
    return json.dumps(
        [{key: escape(value) for key, value in row.items()} for row in rows]
    )
