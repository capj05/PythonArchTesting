"""``forbid_runtime_imports`` judges what the target module itself imports.

A package's ``__init__.py`` that re-exports the application (``from .wiring
import serve``) loads every adapter as soon as any submodule is imported;
those imports are the root package's, not the submodule's.
"""

from __future__ import annotations

import json
from pathlib import Path

from pythonarchtesting.cli import main

_MARKER = (
    "from typing import Annotated\n\n"
    "from pythonarchtesting.rules import forbid_runtime_imports\n\n"
    '__archtest__: Annotated[None, forbid_runtime_imports("sqlite3")]\n\n\n'
)
_BOOKING = "def book(slot):\n    return slot\n"
_STORE = "import sqlite3\n\n\ndef connect():\n    return sqlite3.connect(':memory:')\n"
_WIRING = (
    "from .adapters import store\nfrom .app import booking\n\n\n"
    "def serve():\n    return store, booking\n"
)


def _status(tmp_path: Path, root_init: str, booking: str) -> str:
    for name, files in (
        ("reference", {"__init__.py": "", "app/booking.py": _MARKER + _BOOKING}),
        (
            "target",
            {"__init__.py": root_init, "app/booking.py": booking, "wiring.py": _WIRING},
        ),
    ):
        root = tmp_path / name
        sources = {
            "app/__init__.py": "",
            "adapters/__init__.py": "",
            "adapters/store.py": _STORE,
            **files,
        }
        for rel, text in sources.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(tmp_path / "reference"),
            "--target",
            str(tmp_path / "target"),
            "--dynamic",
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    (status,) = [
        r["status"]
        for t in report["targets"]
        for r in t["results"]
        if "forbid_runtime_imports" in r["rule_id"]
    ]
    return str(status)


def test_imports_of_a_reexporting_root_package_are_not_the_modules(tmp_path: Path):
    assert _status(tmp_path, "from .wiring import serve\n", _BOOKING) == "OK"


def test_the_modules_own_forbidden_import_still_fails(tmp_path: Path):
    booking = "import sqlite3\n\n\n" + _BOOKING
    assert _status(tmp_path, "from .wiring import serve\n", booking) == "FAILED"


def test_a_forbidden_import_through_a_helper_the_module_imports_fails(
    tmp_path: Path,
):
    booking = "from ..adapters import store\n\n\n" + _BOOKING
    assert _status(tmp_path, "", booking) == "FAILED"
