"""``module_interface`` through the CLI (F1.3): a module used only through its interface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pythonarchtesting.cli import main
from tests.integration.test_architecture_cli import _CASES, _SERVICE, _SOLUTION, _write

_MODELS = """
class Order:
    def __init__(self, order_id):
        self.order_id = order_id


def _check(order_id):
    return order_id
"""


def _models(markers: str, body: str = _MODELS) -> str:
    return (
        "from typing import Annotated\n"
        "from pythonarchtesting.rules import module_interface\n"
        + body
        + f"\n__archtest__: Annotated[None, {markers}]\n"
    )


def _run(
    tmp_path: Path,
    markers: str,
    changes: dict[str, str],
    dynamic: bool = False,
    reference_models: str = _MODELS,
) -> dict[str, dict[str, Any]]:
    reference = _write(
        tmp_path / "reference",
        {
            "__init__.py": "",
            **_SOLUTION,
            "models.py": _models(markers, reference_models),
        },
    )
    target = _write(
        tmp_path / "target",
        {"__init__.py": "", **_SOLUTION, "models.py": _MODELS, **changes},
    )
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(reference),
            "--target",
            str(target),
            "--format",
            "json",
            "--output",
            str(output),
            *(["--dynamic"] if dynamic else []),
        ]
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    return {
        r["rule_id"].split("/")[0]: r
        for t in report["targets"]
        for r in t["results"]
        if "module_interface" in r["rule_id"]
    }


_PRIVATE_IMPORT = _SERVICE.replace(
    "from .models import Order", "from .models import Order, _check"
).replace("Order(order_id)", "Order(_check(order_id))")
_ALIAS = _SERVICE.replace(
    "from .models import Order", "from . import models\nfrom .models import Order"
).replace("Order(order_id)", "Order(models._check(order_id))")


def test_public_names_pass(tmp_path: Path):
    assert _run(tmp_path, "module_interface()", {})["DEP005"]["status"] == "OK"


def test_importing_a_private_name_fails_with_its_line(tmp_path: Path):
    result = _run(tmp_path, "module_interface()", {"service.py": _PRIVATE_IMPORT})[
        "DEP005"
    ]

    assert result["status"] == "FAILED"
    assert "_check" in result["details"]["summary"]
    assert "service.py:2" in result["details"]["summary"]


def test_a_private_name_through_the_module_alias_fails(tmp_path: Path):
    result = _run(tmp_path, "module_interface()", {"service.py": _ALIAS})["DEP005"]

    assert result["status"] == "FAILED"
    assert "models._check" in result["details"]["summary"]


def test_an_explicit_interface_rejects_other_public_names(tmp_path: Path):
    models = _MODELS + "\n\ndef helper():\n    return 1\n"
    service = _SERVICE.replace(
        "from .models import Order", "from .models import Order, helper"
    )

    result = _run(
        tmp_path,
        'module_interface("Order")',
        {"models.py": models, "service.py": service},
    )["DEP005"]

    assert result["status"] == "FAILED"
    assert "helper" in result["details"]["summary"]


def test_runtime_part_flags_calls_past_the_interface(tmp_path: Path):
    markers = f'module_interface(entry="controller.handle", cases={_CASES})'

    results = _run(tmp_path, markers, {"service.py": _PRIVATE_IMPORT}, dynamic=True)

    assert results["DYN012"]["status"] == "FAILED"
    assert "_check" in results["DYN012"]["details"]["summary"]


def test_runtime_part_passes_the_solution(tmp_path: Path):
    markers = f'module_interface(entry="controller.handle", cases={_CASES})'

    results = _run(tmp_path, markers, {}, dynamic=True)

    assert results["DYN012"]["status"] == "OK", results["DYN012"]["details"]["summary"]


def test_import_of_the_module_without_alias_is_seen(tmp_path: Path):
    service = _SERVICE.replace(
        "from .models import Order",
        "import target.models\nfrom .models import Order",
    ).replace("Order(order_id)", "Order(target.models._check(order_id))")

    result = _run(tmp_path, "module_interface()", {"service.py": service})["DEP005"]

    assert result["status"] == "FAILED"
    assert "target.models._check" in result["details"]["summary"]


def test_another_module_with_the_same_last_name_is_not_this_one(tmp_path: Path):
    service = "import email.models as m\n" + _SERVICE.replace(
        "        return order\n", "        m._parse = None\n        return order\n"
    )

    result = _run(tmp_path, "module_interface()", {"service.py": service})["DEP005"]

    assert result["status"] == "OK", result["details"]["summary"]


def test_constants_and_imported_names_can_be_listed(tmp_path: Path):
    models = _MODELS + "\nLIMIT = 3\nfrom json import dumps\n"
    service = _SERVICE.replace(
        "from .models import Order", "from .models import Order, LIMIT, dumps"
    )

    result = _run(
        tmp_path,
        'module_interface("Order", "LIMIT", "dumps")',
        {"models.py": models, "service.py": service},
        reference_models=models,
    )

    assert result["DEP005"]["status"] == "OK", result["DEP005"]["details"]


def test_runtime_allows_methods_of_objects_from_the_interface(tmp_path: Path):
    models = (
        _MODELS.replace(
            "        self.order_id = order_id\n",
            "        self.order_id = order_id\n\n"
            "    def label(self):\n        return self.order_id\n",
        )
        + "\n\ndef make(order_id):\n    return Order(order_id)\n"
    )
    service = _SERVICE.replace(
        "from .models import Order", "from .models import make"
    ).replace(
        "order = self.repository.save(Order(order_id))",
        "order = self.repository.save(make(order_id))\n        order.label()",
    )
    markers = f'module_interface("make", entry="controller.handle", cases={_CASES})'

    results = _run(
        tmp_path,
        markers,
        {"models.py": models, "service.py": service},
        dynamic=True,
        reference_models=models,
    )

    assert results["DYN012"]["status"] == "OK", results["DYN012"]["details"]["summary"]


def test_a_private_name_imported_under_the_reference_package_name_fails(
    tmp_path: Path,
):
    # The target directory has another name; the code still imports itself
    # under the reference's (here "reference").
    absolute = _PRIVATE_IMPORT.replace("from .models", "from reference.models")
    result = _run(tmp_path, "module_interface()", {"service.py": absolute})["DEP005"]

    assert result["status"] == "FAILED"
    assert "_check" in result["details"]["summary"]


def test_a_private_name_through_a_module_imported_from_the_package_fails(
    tmp_path: Path,
):
    from_package = _ALIAS.replace("from . import models", "from target import models")
    result = _run(tmp_path, "module_interface()", {"service.py": from_package})[
        "DEP005"
    ]

    assert result["status"] == "FAILED"
    assert "models._check" in result["details"]["summary"]
