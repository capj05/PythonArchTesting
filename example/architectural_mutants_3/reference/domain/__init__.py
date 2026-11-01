"""The clinic's domain: no I/O, no knowledge of the layers above."""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import forbid_imports

__archtest__: Annotated[
    None,
    forbid_imports(
        "ports",
        "application",
        "adapters",
        "api",
        "wiring",
        "sqlite3",
        "pickle",
        scope="package",
        package="domain",
        mode="direct",
    ),
]
