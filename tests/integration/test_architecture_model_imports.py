"""What the architecture model counts as the reference's edges (after T5).

- A call along an import the reference has is allowed at run time, even when
  the reference's cases never make it.
- A subpackage's ``__init__.py`` importing its own submodules (a re-export)
  is no divergence; the root package's still is.
- ``from .pkg import Name`` depends on the module ``pkg`` re-exports ``Name``
  from, not on the package.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pythonarchtesting.cli import main

_ENTRY = (
    "from typing import Annotated\n\n"
    "from pythonarchtesting.rules import architecture_entry\n\n"
    "__archtest__: Annotated[None, architecture_entry({arguments})]\n"
)


def _write(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _results(
    tmp_path: Path,
    reference: dict[str, str],
    target: dict[str, str],
    *flags: str,
) -> dict[str, dict[str, Any]]:
    source = _write(tmp_path / "reference", reference)
    submitted = _write(tmp_path / "target", target)
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(source),
            "--target",
            str(submitted),
            "--format",
            "json",
            "--output",
            str(output),
            *flags,
        ]
    )
    found: dict[str, dict[str, Any]] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            rule_id = str(node.get("rule_id", ""))
            if rule_id.startswith(("DEP004/", "DYN011/")) and "status" in node:
                found[rule_id.split("/")[0]] = node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(output.read_text(encoding="utf-8")))
    return found


_AUDIT = "def log(value):\n    return value\n"
_SERVICE = "class Service:\n" "    def place(self, key):\n" "        return key\n"


def _controller(always: bool) -> str:
    condition = "True" if always else 'request.get("audit")'
    return (
        "from . import audit\n\n\n"
        "def handle(request, service):\n"
        f"    if {condition}:\n"
        '        audit.log(request["id"])\n'
        '    return service.place(request["id"])\n'
    )


def test_a_call_along_an_import_of_the_reference_is_allowed_at_run_time(
    tmp_path: Path,
) -> None:
    cases = '[{"args": [{"id": "A1"}, {"$new": "service.Service"}]}]'
    entry = _ENTRY.format(arguments=f'entry="controller.handle", cases={cases}')
    reference = {
        "__init__.py": entry,
        "audit.py": _AUDIT,
        "service.py": _SERVICE,
        # The reference audits only on request; its case never asks.
        "controller.py": _controller(always=False),
    }
    target = {**reference, "__init__.py": "", "controller.py": _controller(True)}

    result = _results(tmp_path, reference, target, "--dynamic")["DYN011"]

    assert result["status"] == "OK", result["details"]["summary"]
    calls = result["details"]["architecture"]["calls"]
    assert "controller -> audit" in calls["convergent"]
    assert calls["divergent"] == []


_ORDER = "class Order:\n    pass\n"


def test_a_subpackage_re_export_and_an_import_through_it_follow_the_reference(
    tmp_path: Path,
) -> None:
    reference = {
        "__init__.py": _ENTRY.format(arguments=""),
        "domain/__init__.py": "",
        "domain/models.py": _ORDER,
        "service.py": "from .domain.models import Order\n\n\ndef make():\n"
        "    return Order()\n",
    }
    target = {
        "__init__.py": "",
        "domain/__init__.py": "from .models import Order\n",
        "domain/models.py": _ORDER,
        "service.py": "from .domain import Order\n\n\ndef make():\n    return Order()\n",
    }

    result = _results(tmp_path, reference, target)["DEP004"]

    imports = result["details"]["architecture"]["imports"]
    assert result["status"] == "OK", imports["divergent"]
    assert "service -> domain.models" in imports["convergent"]
    assert "domain -> domain.models" in imports["allowed"]


def test_the_root_package_re_export_is_still_a_divergence(tmp_path: Path) -> None:
    reference = {
        "__init__.py": _ENTRY.format(arguments=""),
        "models.py": _ORDER,
    }
    target = {"__init__.py": "from .models import Order\n", "models.py": _ORDER}

    result = _results(tmp_path, reference, target)["DEP004"]

    assert result["status"] == "FAILED"
    assert result["details"]["architecture"]["imports"]["divergent"] == [
        "__init__ -> models"
    ]


def test_importing_a_subpackage_whole_stands_for_its_modules(tmp_path: Path) -> None:
    reference = {
        "__init__.py": _ENTRY.format(arguments=""),
        "api/__init__.py": "",
        "api/handlers.py": "def book():\n    return 1\n",
        "wiring.py": "from .api import handlers\n\n\ndef serve():\n"
        "    return handlers.book()\n",
    }
    target = {
        "__init__.py": "",
        "api/__init__.py": "from .handlers import book\n",
        "api/handlers.py": "def book():\n    return 1\n",
        "wiring.py": "from . import api\n\n\ndef serve():\n    return api.book()\n",
    }

    result = _results(tmp_path, reference, target)["DEP004"]

    imports = result["details"]["architecture"]["imports"]
    assert result["status"] == "OK", imports["divergent"]
    assert "wiring -> api" in imports["convergent"]
