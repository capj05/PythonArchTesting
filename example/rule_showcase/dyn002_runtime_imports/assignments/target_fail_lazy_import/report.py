"""``render`` pulls in ``pickle`` only when it is called.

Importing the module is clean, so ``forbid_runtime_imports`` passes.
``forbid_runtime_calls`` runs ``render`` and sees the call into ``pickle``.
"""

from __future__ import annotations

import json
from xml.sax.saxutils import escape


def render(rows: list[dict[str, str]]) -> str:
    serializer = __import__("pickle")
    _ = serializer.dumps(rows)
    return json.dumps(
        [{key: escape(value) for key, value in row.items()} for row in rows]
    )
