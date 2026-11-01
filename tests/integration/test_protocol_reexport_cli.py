"""``implements_protocol`` follows a class re-exported by a package.

``from ..domain import Appointment`` names the class that ``domain/__init__.py``
imports from ``domain/schedule.py``: an annotation written so is the same type.
"""

from __future__ import annotations

import json
from pathlib import Path

from pythonarchtesting.cli import main

_SCHEDULE = "class Appointment:\n    def cancel(self):\n        return None\n"
_PORT = (
    "from typing import Protocol\n\n"
    "from ..domain.schedule import Appointment\n\n\n"
    "class Store(Protocol):\n"
    "    def add(self, appointment: Appointment) -> None: ...\n"
)
_ADAPTER = (
    "from typing import Annotated\n\n"
    "from pythonarchtesting.rules import implements_protocol\n\n"
    "from ..domain.schedule import Appointment\n"
    "from ..ports.stores import Store\n\n\n"
    "class MemoryStore:\n"
    "    __archtest__: Annotated[None, implements_protocol(Store)]\n\n"
    "    def __init__(self) -> None:\n"
    "        self.items = []\n\n"
    "    def add(self, appointment: Appointment) -> None:\n"
    "        self.items.append(appointment)\n"
)


def _status(tmp_path: Path, adapter: str, domain_init: str) -> str:
    common = {
        "__init__.py": "",
        "domain/schedule.py": _SCHEDULE,
        "ports/__init__.py": "",
        "ports/stores.py": _PORT,
        "adapters/__init__.py": "",
    }
    for name, files in (
        ("reference", {"domain/__init__.py": "", "adapters/memory.py": _ADAPTER}),
        ("target", {"domain/__init__.py": domain_init, "adapters/memory.py": adapter}),
    ):
        for rel, text in {**common, **files}.items():
            path = tmp_path / name / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(tmp_path / "reference"),
            "--target",
            str(tmp_path / "target"),
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
        if "implements_protocol" in r["rule_id"]
    ]
    return str(status)


def test_an_annotation_through_a_package_reexport_is_the_same_type(tmp_path: Path):
    adapter = _ADAPTER.replace(
        "from ..domain.schedule import Appointment", "from ..domain import Appointment"
    )

    assert _status(tmp_path, adapter, "from .schedule import Appointment\n") == "OK"
