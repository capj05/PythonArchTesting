"""``architecture_entry`` through the CLI: the reference as the model (F2).

The reference declares nothing but ``architecture_entry`` in its root
``__init__.py``; the target is compared with the reference's imports (DEP004)
and, with ``--dynamic``, with what the reference does while its entry runs
(DYN011).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pythonarchtesting.cli import main

_CASES = (
    '[{"args": [{"id": "A1"}, {"$new": "service.OrderService", '
    '"args": [{"$new": "repository.OrderRepository"}]}]}]'
)


def _markers(arguments: str = "") -> str:
    return (
        "from typing import Annotated\n\n"
        "from pythonarchtesting.rules import architecture_entry\n\n"
        f"__archtest__: Annotated[None, architecture_entry({arguments})]\n"
    )


_RUNTIME = f'entry="controller.handle", cases={_CASES}'

_MODELS = """
class Order:
    def __init__(self, order_id):
        self.order_id = order_id
"""

_REPOSITORY = """
import json


class OrderRepository:
    def __init__(self):
        self.saved = []

    def save(self, order):
        self.saved.append(json.dumps({"id": order.order_id}))
        return order
"""

_SERVICE = """
from .models import Order


class OrderService:
    def __init__(self, repository):
        self.repository = repository

    def place(self, order_id, notify=None):
        order = self.repository.save(Order(order_id))
        if notify is not None:
            notify(order)
        return order
"""

_CONTROLLER = """
def handle(request, service):
    return service.place(request["id"])
"""

_APP = """
from .repository import OrderRepository
from .service import OrderService


def build():
    return OrderService(OrderRepository())
"""

_SOLUTION = {
    "models.py": _MODELS,
    "repository.py": _REPOSITORY,
    "service.py": _SERVICE,
    "controller.py": _CONTROLLER,
    "app.py": _APP,
}


def _write(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True)
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def _architecture_results(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
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

    walk(report)
    return found


def run_architecture(
    tmp_path: Path,
    changes: dict[str, str | None],
    *,
    markers: str | None = None,
    flags: tuple[str, ...] = (),
) -> dict[str, dict[str, Any]]:
    """Run the CLI on the solution with ``changes`` (``None`` deletes a file)."""
    init = _markers() if markers is None else markers
    reference = _write(tmp_path / "reference", {"__init__.py": init, **_SOLUTION})
    files: dict[str, str] = {"__init__.py": "", **_SOLUTION}
    for name, text in changes.items():
        if text is None:
            files.pop(name, None)
        else:
            files[name] = text
    target = _write(tmp_path / "target", files)
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
            *flags,
        ]
    )
    return _architecture_results(json.loads(output.read_text(encoding="utf-8")))


def test_same_imports_pass(tmp_path: Path):
    result = run_architecture(tmp_path, {})["DEP004"]

    assert result["status"] == "OK"
    assert result["details"]["architecture"]["imports"]["divergent"] == []
    assert (
        "service -> models"
        in result["details"]["architecture"]["imports"]["convergent"]
    )


def test_controller_importing_the_repository_fails(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {"controller.py": "from .repository import OrderRepository\n" + _CONTROLLER},
    )["DEP004"]

    assert result["status"] == "FAILED"
    assert result["details"]["architecture"]["imports"]["divergent"] == [
        "controller -> repository"
    ]
    assert "controller -> repository" in result["details"]["summary"]
    assert "controller.py:1" in result["details"]["summary"]


_HELPER = "from .repository import OrderRepository\n\n\ndef make():\n    return 1\n"
_CONTROLLER_WITH_HELPER = "from .responses import ok\n" + _CONTROLLER


def test_helper_module_is_folded_by_default(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {
            "controller.py": _CONTROLLER_WITH_HELPER,
            "responses.py": "def ok(value):\n    return value\n",
        },
    )["DEP004"]

    assert result["status"] == "OK"


def test_helper_reaching_past_the_service_fails(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {"controller.py": _CONTROLLER_WITH_HELPER, "responses.py": _HELPER},
    )["DEP004"]

    assert result["status"] == "FAILED"
    assert result["details"]["architecture"]["imports"]["divergent"] == [
        "controller -> repository"
    ]


def test_helper_module_fails_under_strict(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {
            "controller.py": _CONTROLLER_WITH_HELPER,
            "responses.py": "def ok(value):\n    return value\n",
        },
        markers=_markers('policy="strict"'),
    )["DEP004"]

    assert result["status"] == "FAILED"
    assert result["details"]["architecture"]["imports"]["divergent"] == [
        "controller -> responses"
    ]


def test_new_package_fails(tmp_path: Path):
    result = run_architecture(tmp_path, {"service.py": "import pickle\n" + _SERVICE})[
        "DEP004"
    ]

    assert result["status"] == "FAILED"
    assert result["details"]["architecture"]["external"]["divergent"] == [
        "service -> pickle"
    ]


def test_a_package_the_reference_uses_elsewhere_passes(tmp_path: Path):
    result = run_architecture(tmp_path, {"service.py": "import json\n" + _SERVICE})[
        "DEP004"
    ]

    assert result["status"] == "OK"


def test_future_import_is_ignored(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {"controller.py": "from __future__ import annotations\n" + _CONTROLLER},
    )["DEP004"]

    assert result["status"] == "OK"
    assert result["details"]["architecture"]["external"]["divergent"] == []


def test_renamed_target_module_is_judged_by_reference_names(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {
            "repository.py": None,
            "storage.py": _REPOSITORY,
            "app.py": _APP.replace(".repository", ".storage"),
        },
    )["DEP004"]

    assert result["status"] == "OK", result["details"]["summary"]


def test_layered_extra_downward_import_is_undecided(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {"controller.py": "from .models import Order\n" + _CONTROLLER},
        markers=_markers('policy="layered"'),
    )["DEP004"]

    assert result["status"] == "OK"
    assert result["details"]["undecided"] == ["imports: controller -> models"]
    assert "1 undecided" in result["details"]["summary"]


def test_layered_upward_import_fails(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {"models.py": "from . import service\n" + _MODELS},
        markers=_markers('policy="layered"'),
    )["DEP004"]

    assert result["status"] == "FAILED"
    assert result["details"]["architecture"]["imports"]["divergent"] == [
        "models -> service"
    ]


def test_allowed_exception_passes(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {"controller.py": "from .repository import OrderRepository\n" + _CONTROLLER},
        markers=_markers('allow=["controller -> repository"]'),
    )["DEP004"]

    assert result["status"] == "OK"
    assert result["details"]["architecture"]["imports"]["allowed"] == [
        "controller -> repository"
    ]


def test_architecture_flag_catches_a_layer_import_without_markers(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {"controller.py": "from .repository import OrderRepository\n" + _CONTROLLER},
        markers="",
        flags=("--architecture",),
    )["DEP004"]

    assert result["status"] == "FAILED"


def test_without_flag_or_markers_no_architecture_rule_runs(tmp_path: Path):
    assert run_architecture(tmp_path, {}, markers="") == {}


def _runtime(tmp_path: Path, changes: dict[str, str | None]) -> dict[str, Any]:
    return run_architecture(
        tmp_path, changes, markers=_markers(_RUNTIME), flags=("--dynamic",)
    )["DYN011"]


def test_reference_behaviour_passes_at_run_time(tmp_path: Path):
    result = _runtime(tmp_path, {})

    assert result["status"] == "OK", result["details"]["summary"]
    architecture = result["details"]["architecture"]
    assert "controller -> service" in architecture["calls"]["convergent"]
    assert "service -> models.Order" in architecture["instances"]["convergent"]
    assert "repository -> json" in architecture["external"]["convergent"]


def test_bypass_call_fails(tmp_path: Path):
    result = _runtime(
        tmp_path,
        {
            "controller.py": "def handle(request, service):\n"
            '    service.repository.save(request["id"])\n'
            '    return service.place(request["id"])\n'
        },
    )

    assert result["status"] == "FAILED"
    assert result["details"]["architecture"]["calls"]["divergent"] == [
        "controller -> repository"
    ]


def test_service_building_its_repository_fails(tmp_path: Path):
    result = _runtime(
        tmp_path,
        {
            "service.py": _SERVICE.replace(
                "order = self.repository.save(Order(order_id))",
                "from .repository import OrderRepository\n\n"
                "        order = OrderRepository().save(Order(order_id))",
            )
        },
    )

    assert result["status"] == "FAILED"
    assert (
        "service -> repository.OrderRepository"
        in result["details"]["architecture"]["instances"]["divergent"]
    )


def test_pickle_through_importlib_fails(tmp_path: Path):
    result = _runtime(
        tmp_path,
        {
            "service.py": "import importlib\n"
            + _SERVICE.replace(
                "        return order\n",
                '        importlib.import_module("pickle").dumps(order_id)\n'
                "        return order\n",
            )
        },
    )

    assert result["status"] == "FAILED"
    divergent = result["details"]["architecture"]["external"]["divergent"]
    assert "service -> pickle" in divergent


def test_unmatched_class_instance_is_undecided(tmp_path: Path):
    result = _runtime(
        tmp_path,
        {
            "receipts.py": "class Receipt:\n    def __init__(self, order):\n"
            "        self.order = order\n",
            "service.py": "from .receipts import Receipt\n"
            + _SERVICE.replace(
                "        return order\n",
                "        Receipt(order)\n        return order\n",
            ),
        },
    )

    assert result["status"] == "OK", result["details"]["summary"]
    assert result["details"]["undecided"] == ["instances: service -> receipts.Receipt"]


def test_runtime_rule_is_skipped_without_dynamic(tmp_path: Path):
    results = run_architecture(tmp_path, {}, markers=_markers(_RUNTIME))

    assert results["DEP004"]["status"] == "OK"
    assert results["DYN011"]["status"] == "SKIPPED"


def test_undecided_changes_are_warned_about_and_summarised(tmp_path: Path, capsys):
    from pythonarchtesting.mcp_server.reports import summarize_report

    run_architecture(
        tmp_path,
        {"controller.py": "from .models import Order\n" + _CONTROLLER},
        markers=_markers('policy="layered"'),
    )

    assert (
        "warning: 1 result(s) passed with undecided architecture changes; "
        "see details.undecided"
    ) in capsys.readouterr().err
    assert summarize_report(str(tmp_path / "report.json"))["undecided_total"] == 1


def test_count_results_undecided_counts_only_passes_with_undecided():
    from types import SimpleNamespace

    from pythonarchtesting.runner.skips import count_results_undecided

    def result(status: str, undecided: list[str] | None) -> SimpleNamespace:
        details = {"undecided": undecided} if undecided is not None else {}
        return SimpleNamespace(status=status, details=details)

    states = [
        SimpleNamespace(
            rule_results=[
                result("OK", ["imports: a -> b"]),
                result("OK", []),
                result("OK", None),
                result("FAILED", ["imports: a -> b"]),
            ]
        )
    ]

    assert count_results_undecided(states) == 1


def test_names_imported_from_the_root_package_are_not_libraries(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {
            "__init__.py": "def helper():\n    return 1\n",
            "controller.py": "from . import helper\n" + _CONTROLLER,
        },
    )["DEP004"]

    assert result["details"]["architecture"]["external"]["divergent"] == []


def test_absolute_imports_through_the_own_package_are_internal(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {"service.py": _SERVICE.replace("from .models", "from target.models")},
    )["DEP004"]

    assert result["status"] == "OK", result["details"]["summary"]
    imports = result["details"]["architecture"]["imports"]
    assert "service -> models" in imports["convergent"]
    assert result["details"]["architecture"]["external"]["divergent"] == []


_SKIPS_SERVICE = {
    "controller.py": "def handle(request, service):\n    return request\n"
}


def test_a_call_the_target_no_longer_makes_is_only_absent_by_default(tmp_path: Path):
    result = run_architecture(
        tmp_path, _SKIPS_SERVICE, markers=_markers(_RUNTIME), flags=("--dynamic",)
    )["DYN011"]

    assert result["status"] == "OK", result["details"]["summary"]
    assert (
        "controller -> service" in result["details"]["architecture"]["calls"]["absent"]
    )


def test_require_all_fails_on_a_call_the_target_no_longer_makes(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        _SKIPS_SERVICE,
        markers=_markers(f"require_all=True, {_RUNTIME}"),
        flags=("--dynamic",),
    )["DYN011"]

    assert result["status"] == "FAILED"
    assert any(
        "controller -> service" in item and "never" in item
        for item in result["details"]["violations"]
    )


def test_markdown_report_has_an_architecture_section(tmp_path: Path):
    reference = _write(
        tmp_path / "reference",
        {"__init__.py": _markers('policy="layered"'), **_SOLUTION},
    )
    target = _write(
        tmp_path / "target",
        {
            "__init__.py": "",
            **_SOLUTION,
            "controller.py": "from .models import Order\n" + _CONTROLLER,
        },
    )
    output = tmp_path / "markdown"
    main(
        [
            "--source",
            str(reference),
            "--target",
            str(target),
            "--format",
            "markdown",
            "--output",
            str(output),
        ]
    )

    (page,) = list(output.rglob("targets/*.md"))
    text = page.read_text(encoding="utf-8")
    assert "## Architecture" in text
    assert "### Static (DEP004): OK" in text
    assert "- Undecided (to review): imports `controller -> models`" in text
    assert "- Passed With Undecided Architecture Changes: 1" in text
    assert text.index("## Architecture") < text.index("## Results")
    index = next(output.rglob("report.md")).read_text(encoding="utf-8")
    assert "- Passed With Undecided Architecture Changes: 1" in index


def test_static_divergences_are_structured(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {"controller.py": "from .repository import OrderRepository\n" + _CONTROLLER},
    )["DEP004"]

    assert result["details"]["divergences"] == [
        {
            "kind": "divergent",
            "layer": "imports",
            "edge": "controller -> repository",
            "file": "controller.py",
            "module": "controller",
            "line": 1,
        }
    ]


def test_runtime_divergences_are_structured(tmp_path: Path):
    result = _runtime(
        tmp_path,
        {
            "controller.py": "def handle(request, service):\n"
            '    service.repository.save(request["id"])\n'
            '    return service.place(request["id"])\n'
        },
    )

    (item,) = result["details"]["divergences"]
    assert item["layer"] == "calls"
    assert item["edge"] == "controller -> repository"
    assert item["module"] == "controller"
    assert item["line"] == 2


def test_explain_target_carries_feedback(tmp_path: Path):
    from pythonarchtesting.mcp_server.reports import explain_target

    run_architecture(
        tmp_path,
        {"controller.py": "from .repository import OrderRepository\n" + _CONTROLLER},
    )

    explained = explain_target(str(tmp_path / "report.json"), "target")
    (item,) = [r for r in explained["results"] if r["rule"].startswith("DEP004")]

    assert item["feedback"]["issues"][0]["edge"] == "controller -> repository"


def _check(
    tmp_path: Path, changes: dict[str, str | None], **kwargs: Any
) -> dict[str, Any]:
    from pythonarchtesting.mcp_server.evaluation import check_architecture

    reference = _write(
        tmp_path / "reference", {"__init__.py": _markers(_RUNTIME), **_SOLUTION}
    )
    files: dict[str, str] = {"__init__.py": "", **_SOLUTION}
    for name, text in changes.items():
        if text is None:
            files.pop(name, None)
        else:
            files[name] = text
    target = _write(tmp_path / "target", files)
    return check_architecture(str(reference), str(target), **kwargs)


def test_check_architecture_passes_a_clean_target(tmp_path: Path):
    result = _check(tmp_path, {})

    assert result["passed"] is True
    assert result["problems"] == []
    assert result["mode"] == "static"


def test_check_architecture_reports_problems_with_feedback(tmp_path: Path):
    result = _check(
        tmp_path,
        {"controller.py": "from .repository import OrderRepository\n" + _CONTROLLER},
    )

    assert result["passed"] is False
    (problem,) = [p for p in result["problems"] if p["rule"].startswith("DEP004")]
    assert problem["feedback"]["issues"][0]["edge"] == "controller -> repository"
    assert not (tmp_path / "report.json").exists()


def test_check_architecture_full_mode_runs_the_runtime_comparison(tmp_path: Path):
    result = _check(
        tmp_path,
        {
            "controller.py": "def handle(request, service):\n"
            '    service.repository.save(request["id"])\n'
            '    return service.place(request["id"])\n'
        },
        mode="full",
        sandbox="limits",
    )

    assert result["passed"] is False
    assert any(p["rule"].startswith("DYN011") for p in result["problems"])


def test_check_architecture_rejects_an_unknown_mode(tmp_path: Path):
    import pytest

    from pythonarchtesting.mcp_server.errors import ToolInputError

    with pytest.raises(ToolInputError, match="mode"):
        _check(tmp_path, {}, mode="fast")


def test_runtime_divergences_name_the_target_file(tmp_path: Path):
    result = _runtime(
        tmp_path,
        {
            "controller.py": "def handle(request, service):\n"
            '    service.repository.save(request["id"])\n'
            '    return service.place(request["id"])\n'
        },
    )

    (item,) = result["details"]["divergences"]
    assert item["file"] == "controller.py"


def test_absent_calls_point_into_the_reference_not_the_target(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {"controller.py": "def handle(request, service):\n    return request\n"},
        markers=_markers(f"require_all=True, {_RUNTIME}"),
        flags=("--dynamic",),
    )["DYN011"]

    absent = [d for d in result["details"]["divergences"] if d["kind"] == "absent"]
    assert absent
    for item in absent:
        assert item["file"] is None and item["line"] is None and item["module"] is None
        assert item["reference_module"] and item["reference_line"]


def test_check_architecture_reports_applied_and_refused_pairs(tmp_path: Path):
    result = _check(
        tmp_path,
        {"controller.py": None, "web.py": _CONTROLLER},
        mapping={"pairs": {"controller": "nosuch", "models": "models"}},
    )

    refused = result["mapping"]["refused"]
    assert [item["pair"] for item in refused] == ["controller -> nosuch"]
    assert "nosuch" in refused[0]["reason"]


def test_check_architecture_says_whether_every_check_ran(tmp_path: Path):
    result = _check(tmp_path, {})

    assert result["passed"] is True
    assert result["complete"] is False  # the runtime part is SKIPPED in static mode


def test_explain_rule_rows_carry_feedback(tmp_path: Path):
    from pythonarchtesting.mcp_server.reports import explain_rule

    run_architecture(
        tmp_path,
        {"controller.py": "from .repository import OrderRepository\n" + _CONTROLLER},
    )

    explained = explain_rule(
        str(tmp_path / "report.json"), "DEP004/architecture_entry/v1"
    )
    (row,) = [r for r in explained["targets"] if r["status"] == "FAILED"]

    assert row["feedback"]["issues"][0]["edge"] == "controller -> repository"


def test_a_library_used_by_a_new_helper_counts_for_its_caller(tmp_path: Path):
    helper = "import pickle\n\n\ndef snapshot(order):\n    return pickle.dumps(order.order_id)\n"
    service = _SERVICE.replace(
        "from .models import Order",
        "from .models import Order\nfrom .snap import snapshot",
    ).replace(
        "        return order\n", "        snapshot(order)\n        return order\n"
    )
    result = run_architecture(
        tmp_path,
        {"service.py": service, "snap.py": helper},
        markers=_markers(f'forbid=["service -> pickle"], {_RUNTIME}'),
        flags=("--dynamic",),
    )["DYN011"]

    assert (
        "service -> pickle"
        in result["details"]["architecture"]["external"]["divergent"]
    )


def test_classes_of_the_root_package_are_named_at_run_time(tmp_path: Path):
    init = (
        "class Receipt:\n    def __init__(self, order):\n        self.order = order\n"
    )
    service = _SERVICE.replace(
        "from .models import Order", "from .models import Order\nfrom . import Receipt"
    ).replace(
        "        return order\n", "        Receipt(order)\n        return order\n"
    )
    reference = {"__init__.py": _markers(_RUNTIME) + "\n" + init, "service.py": service}

    result = _check_root(
        tmp_path, reference, {"__init__.py": init, "service.py": service}
    )

    assert result["undecided"] == [], result["undecided"]


def _check_root(
    tmp_path: Path, reference_files: dict[str, str], target_files: dict[str, str]
) -> dict[str, Any]:
    reference = _write(tmp_path / "reference", {**_SOLUTION, **reference_files})
    target = _write(tmp_path / "target", {**_SOLUTION, **target_files})
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
            "--dynamic",
        ]
    )
    (result,) = [
        r
        for t in json.loads(output.read_text(encoding="utf-8"))["targets"]
        for r in t["results"]
        if r["rule_id"].startswith("DYN011")
    ]
    return {
        "status": result["status"],
        "undecided": result["details"].get("undecided", []),
    }


def test_check_architecture_separates_reference_problems(tmp_path: Path):
    from pythonarchtesting.mcp_server.evaluation import check_architecture

    reference = _write(
        tmp_path / "reference",
        {"__init__.py": _markers('policy="nonsense"'), **_SOLUTION},
    )
    target = _write(tmp_path / "target", {"__init__.py": "", **_SOLUTION})

    result = check_architecture(str(reference), str(target))

    assert result["reference_problems"]
    assert "policy" in result["reference_problems"][0]["summary"]
    assert all("invalid_declaration" not in p["rule"] for p in result["problems"])
    # Nothing in the target can fix the reference: a clean target passes.
    assert result["problems"] == []
    assert result["passed"] is True


def test_divergences_are_capped_but_counted(tmp_path: Path):
    imports = "".join(f"import mod{i}\n" for i in range(30))
    result = run_architecture(tmp_path, {"controller.py": imports + _CONTROLLER})[
        "DEP004"
    ]

    assert len(result["details"]["divergences"]) == 25
    assert result["details"]["divergence_count"] == 30


def test_markdown_report_shows_matrices_metrics_and_static_vs_runtime(
    tmp_path: Path,
):
    reference = _write(
        tmp_path / "reference",
        {"__init__.py": _markers(_RUNTIME), **_SOLUTION},
    )
    target = _write(tmp_path / "target", {"__init__.py": "", **_SOLUTION})
    output = tmp_path / "markdown"
    main(
        [
            "--source",
            str(reference),
            "--target",
            str(target),
            "--format",
            "markdown",
            "--output",
            str(output),
            "--dynamic",
        ]
    )

    (page,) = list(output.rglob("targets/*.md"))
    text = page.read_text(encoding="utf-8")
    assert "#### Dependency Matrix: imports" in text
    assert "#### Dependency Matrix: calls" in text
    assert "#### Module Metrics (informative, not part of the verdict)" in text
    assert "### Static vs Runtime" in text
    # The service gets its repository injected: called, never imported.
    assert "`service -> repository` (also in the reference)" in text


def test_markdown_index_aggregates_divergences_across_targets(tmp_path: Path):
    reference = _write(tmp_path / "reference", {"__init__.py": _markers(), **_SOLUTION})
    bypass = "from .repository import OrderRepository\n" + _CONTROLLER
    for name in ("one", "two", "three"):
        _write(
            tmp_path / "targets" / name,
            {"__init__.py": "", **_SOLUTION, "controller.py": bypass},
        )
    output = tmp_path / "markdown"
    main(
        [
            "--source",
            str(reference),
            "--targets-dir",
            str(tmp_path / "targets"),
            "--format",
            "markdown",
            "--output",
            str(output),
        ]
    )

    index = next(output.rglob("report.md")).read_text(encoding="utf-8")
    assert "## Architecture Across Targets" in index
    assert (
        "| imports | divergent | `controller -> repository` | 3/3 (100%) "
        "| check the model |"
    ) in index


def _run_projects(
    tmp_path: Path,
    reference_files: dict[str, str],
    target_files: dict[str, str],
    *,
    names: tuple[str, str] = ("reference", "target"),
    flags: tuple[str, ...] = (),
) -> dict[str, dict[str, Any]]:
    reference = _write(tmp_path / names[0], reference_files)
    target = _write(tmp_path / names[1], target_files)
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
            *flags,
        ]
    )
    return _architecture_results(json.loads(output.read_text(encoding="utf-8")))


_AUDIT = 'def audit(value):\n    return f"audit:{value}"\n'


def test_a_call_into_an_entity_moved_out_of_the_root_package_keeps_its_name(
    tmp_path: Path,
):
    declaration = _markers(
        'entry="controller.handle", cases=[{"args": [3]}], require_all=True'
    )
    reference = {
        "__init__.py": _AUDIT + declaration,
        "controller.py": "def handle(value):\n    from . import audit\n"
        "    return audit(value)\n",
    }
    target = {
        "__init__.py": "",
        "util.py": _AUDIT,
        "controller.py": "def handle(value):\n    from .util import audit\n"
        "    return audit(value)\n",
    }

    result = _run_projects(tmp_path, reference, target, flags=("--dynamic",))["DYN011"]

    assert result["status"] == "OK", result["details"]["summary"]
    calls = result["details"]["architecture"]["calls"]
    assert "controller -> __init__" in calls["convergent"]


_SQL_SERVICE = (
    'import sqlite3\n\n\ndef save(x):\n    return sqlite3.connect(":memory:")\n'
)
_SQL_REFERENCE = {
    "__init__.py": _markers('forbid=["controller -> sqlite3"]'),
    "controller.py": "from . import service\n\n\ndef handle(x):\n"
    "    return service.save(x)\n",
    "service.py": _SQL_SERVICE,
}


def test_a_forbidden_library_used_through_a_new_helper_module_fails(tmp_path: Path):
    target = {
        "__init__.py": "",
        "service.py": _SQL_SERVICE,
        "helper.py": 'import sqlite3\n\n\ndef conn():\n    return sqlite3.connect(":memory:")\n',
        "controller.py": "from . import helper, service\n\n\ndef handle(x):\n"
        "    helper.conn()\n    return service.save(x)\n",
    }

    result = _run_projects(tmp_path, _SQL_REFERENCE, target)["DEP004"]

    assert result["status"] == "FAILED"
    assert (
        "controller -> sqlite3"
        in result["details"]["architecture"]["external"]["divergent"]
    )


def test_a_forbidden_edge_says_it_is_forbidden(tmp_path: Path):
    target = {
        "__init__.py": "",
        "service.py": _SQL_SERVICE,
        "controller.py": "import sqlite3\n\nfrom . import service\n\n\n"
        "def handle(x):\n    return service.save(x)\n",
    }

    result = _run_projects(tmp_path, _SQL_REFERENCE, target)["DEP004"]

    assert result["status"] == "FAILED"
    text = " ".join(str(item) for item in result["details"]["violations"])
    assert "forbidden" in text
    assert "the reference uses no sqlite3" not in text


def test_imports_through_the_reference_package_name_are_internal(tmp_path: Path):
    files = {
        "__init__.py": "",
        "service.py": "def place(x):\n    return x\n",
        "controller.py": "from shop import service\n\n\ndef handle(x):\n"
        "    return service.place(x)\n",
    }

    result = _run_projects(
        tmp_path,
        {**files, "__init__.py": _markers()},
        files,
        names=("shop", "student_7"),
    )["DEP004"]

    assert result["status"] == "OK", result["details"]["summary"]
    assert (
        "controller -> service"
        in result["details"]["architecture"]["imports"]["convergent"]
    )


def test_a_forbidden_runtime_call_says_it_is_forbidden(tmp_path: Path):
    result = run_architecture(
        tmp_path,
        {
            "controller.py": "from . import models\n\n\n"
            "def handle(request, service):\n"
            "    models.Order(request['id'])\n"
            "    return service.place(request['id'])\n"
        },
        markers=_markers(f'forbid=["controller -> models"], {_RUNTIME}'),
        flags=("--dynamic",),
    )["DYN011"]

    assert result["status"] == "FAILED"
    text = " ".join(str(item) for item in result["details"]["violations"])
    assert "forbids" in text
