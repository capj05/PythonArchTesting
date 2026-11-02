"""The driving side: requests in, responses out."""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import forbid_imports

__archtest__: Annotated[
    None,
    forbid_imports(
        "adapters",
        "domain",
        "ports",
        "wiring",
        "sqlite3",
        "pickle",
        scope="package",
        package="api",
        mode="direct",
    ),
]
