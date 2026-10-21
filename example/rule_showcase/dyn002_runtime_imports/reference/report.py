"""Reference report module for the DYN002 ``forbid_runtime_imports`` showcase.

The report layer must not reach the storage layer (``sqlite3``, ``pickle``) or
XML parsing, though ``xml.sax.saxutils`` is allowed for escaping. Two markers
cover the two moments an import can happen:

- ``forbid_runtime_imports`` imports the module and records what its code
  imports meanwhile, including ``importlib.import_module`` and ``__import__``
  calls that static analysis cannot resolve;
- ``forbid_runtime_calls`` on ``render`` runs it and catches a module that is
  pulled in lazily and then used, which importing the module never shows.
"""

from __future__ import annotations

import json
from typing import Annotated
from xml.sax.saxutils import escape

from pythonarchtesting.rules import forbid_runtime_calls, forbid_runtime_imports

__archtest__: Annotated[
    None,
    forbid_runtime_imports("sqlite3", "pickle", "xml", allow=["xml.sax.saxutils"]),
]


def render(rows: list[dict[str, str]]) -> str:
    __archtest__: Annotated[  # noqa: F842
        None,
        forbid_runtime_calls(
            "sqlite3",
            "pickle",
            cases=[{"args": [[{"name": "a<b"}]]}],
        ),
    ]
    return json.dumps(
        [{key: escape(value) for key, value in row.items()} for row in rows]
    )
