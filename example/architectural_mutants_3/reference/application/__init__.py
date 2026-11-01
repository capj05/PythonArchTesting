"""The use cases, written against the ports only."""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import forbid_imports

__archtest__: Annotated[
    None,
    forbid_imports(
        "adapters",
        "api",
        "wiring",
        "sqlite3",
        "pickle",
        scope="package",
        package="application",
        mode="direct",
    ),
]
