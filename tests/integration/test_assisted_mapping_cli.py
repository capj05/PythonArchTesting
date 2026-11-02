"""Assisted pairing (F4.4): a mapping file pairs what the matching could not."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pythonarchtesting.cli import main
from tests.integration.test_architecture_cli import (
    _CONTROLLER,
    _RUNTIME,
    _SOLUTION,
    _markers,
    _write,
)

# The controller, renamed and rewritten the way a student would: the matching
# cannot pair handle with the reference's (other module, other body).
_HANDLER = """
def handle(request, service):
    order_id = request["id"]
    placed = service.place(order_id)
    return placed
"""


def _run(
    tmp_path: Path,
    mapping: dict[str, Any] | None,
    files: dict[str, str | None],
    name_fallback: bool = False,
) -> dict[str, Any]:
    """Run with the pairing by name off by default: these tests are about what
    a mapping does where the automatic matching leaves an entity unpaired."""
    reference = _write(
        tmp_path / "reference", {"__init__.py": _markers(_RUNTIME), **_SOLUTION}
    )
    target_files: dict[str, str] = {"__init__.py": "", **_SOLUTION}
    for name, text in files.items():
        if text is None:
            target_files.pop(name, None)
        else:
            target_files[name] = text
    target = _write(tmp_path / "target", target_files)
    output = tmp_path / "report.json"
    arguments = [
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
    if not name_fallback:
        config = tmp_path / "matching.conf"
        config.write_text("[matching]\nname_fallback = false\n", encoding="utf-8")
        arguments += ["--config", str(config)]
    if mapping is not None:
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text(json.dumps(mapping), encoding="utf-8")
        arguments += ["--mapping", str(mapping_file)]
    main(arguments)
    return json.loads(output.read_text(encoding="utf-8"))["targets"][0]


def _status(target: dict[str, Any], prefix: str) -> str:
    (result,) = [r for r in target["results"] if r["rule_id"].startswith(prefix)]
    return str(result["status"]) + ":" + str(result["details"].get("reason"))


def _match(target: dict[str, Any], source_part: str) -> dict[str, Any]:
    return next(
        m for m in target["matching"]["matches"] if source_part in m["source_entity_id"]
    )


_RENAMED = {"controller.py": None, "handler.py": _HANDLER}


def test_without_a_mapping_the_renamed_entry_is_not_paired(tmp_path: Path):
    target = _run(tmp_path, None, _RENAMED)

    assert _status(target, "DYN011") == "FAILED:required_target_missing"


def test_by_default_the_only_entry_of_its_name_is_paired_by_name(tmp_path: Path):
    target = _run(tmp_path, None, _RENAMED, name_fallback=True)

    assert _status(target, "DYN011") == "OK:no_violations"
    codes = [
        r["code"] for r in _match(target, ":controller:handle:function:")["reasons"]
    ]
    assert "unique_name" in codes


def test_a_module_pair_pairs_its_entities_by_name(tmp_path: Path):
    target = _run(tmp_path, {"pairs": {"controller": "handler"}}, _RENAMED)

    assert _status(target, "DYN011").startswith("OK")
    match = _match(target, ":controller:handle:function:")
    assert match["status"] == "matched"
    assert ":handler:handle:function:" in match["target_entity_id"]
    assert any(r["code"] == "assisted_mapping" for r in match["reasons"])


def test_an_entity_pair_is_applied(tmp_path: Path):
    target = _run(
        tmp_path,
        {"pairs": {"controller.handle": "handler.handle"}},
        _RENAMED,
    )

    assert _status(target, "DYN011").startswith("OK")


def test_a_pair_of_different_kinds_is_rejected_and_says_why(tmp_path: Path):
    target = _run(
        tmp_path, {"pairs": {"controller.handle": "service.OrderService"}}, _RENAMED
    )

    match = _match(target, ":controller:handle:function:")
    assert match["status"] != "matched"
    (rejected,) = [
        r for r in match["reasons"] if r["code"] == "assisted_mapping_rejected"
    ]
    assert "kind" in rejected["message"]


def test_a_pair_that_cannot_be_called_like_the_reference_is_rejected(tmp_path: Path):
    files = {
        "controller.py": None,
        "handler.py": "def handle(request):\n    return request\n",
    }

    target = _run(tmp_path, {"pairs": {"controller.handle": "handler.handle"}}, files)

    match = _match(target, ":controller:handle:function:")
    assert match["status"] != "matched"
    (rejected,) = [
        r for r in match["reasons"] if r["code"] == "assisted_mapping_rejected"
    ]
    assert "signature" in rejected["message"]


def test_an_automatic_match_is_never_overridden(tmp_path: Path):
    target = _run(
        tmp_path,
        {"pairs": {"service.OrderService": "repository.OrderRepository"}},
        {"controller.py": _CONTROLLER},
    )

    match = _match(target, ":service:OrderService:class:")
    assert ":service:OrderService:class:" in match["target_entity_id"]
    assert any(r["code"] == "assisted_mapping_rejected" for r in match["reasons"])


def test_a_mapping_can_name_the_target_it_is_for(tmp_path: Path):
    target = _run(
        tmp_path,
        {"targets": {"target": {"pairs": {"controller": "handler"}}}},
        _RENAMED,
    )

    assert _status(target, "DYN011").startswith("OK")


def test_propose_mapping_lists_unpaired_reference_entities_with_candidates(
    tmp_path: Path,
):
    from pythonarchtesting.mcp_server.reports import propose_mapping

    _run(tmp_path, None, _RENAMED)

    proposal = propose_mapping(str(tmp_path / "report.json"), "target")

    unpaired = {item["reference"]: item for item in proposal["unpaired"]}
    assert set(unpaired) == {"controller", "controller.handle"}
    assert unpaired["controller.handle"]["kind"] == "function"
    assert unpaired["controller.handle"]["candidates"][0]["target"] == "handler.handle"
    assert proposal["mapping_template"] == {"pairs": {}}


def test_mcp_run_evaluation_accepts_a_mapping(tmp_path: Path):
    from pythonarchtesting.mcp_server.evaluation import run_evaluation

    reference = _write(tmp_path / "reference", {"__init__.py": _markers(), **_SOLUTION})
    target_files: dict[str, str] = {
        "__init__.py": "",
        **_SOLUTION,
        "handler.py": _HANDLER,
    }
    target_files.pop("controller.py")
    target = _write(tmp_path / "target", target_files)

    result = run_evaluation(
        str(reference),
        str(tmp_path / "out"),
        targets=[str(target)],
        mapping={"pairs": {"controller": "handler"}},
    )
    report = json.loads(Path(result["report_json"]).read_text(encoding="utf-8"))
    match = _match(report["targets"][0], ":controller:handle:function:")

    assert match["status"] == "matched"


def test_a_target_already_paired_with_another_entity_is_refused(tmp_path: Path):
    target = _run(
        tmp_path,
        {"pairs": {"controller.handle": "app.build"}},
        {"controller.py": None, "handler.py": _HANDLER},
    )

    match = _match(target, ":controller:handle:function:")
    assert match["status"] != "matched"
    (rejected,) = [
        r for r in match["reasons"] if r["code"] == "assisted_mapping_rejected"
    ]
    assert "already" in rejected["message"]


def test_an_unknown_reference_name_is_an_error(tmp_path: Path, capsys):
    import pytest

    with pytest.raises(SystemExit):
        _run(tmp_path, {"pairs": {"controler": "handler"}}, _RENAMED)
    assert "controler" in capsys.readouterr().err


def test_a_mapping_comes_before_pairing_by_name(tmp_path: Path):
    target = _run(
        tmp_path, {"pairs": {"controller": "handler"}}, _RENAMED, name_fallback=True
    )

    codes = [
        r["code"] for r in _match(target, ":controller:handle:function:")["reasons"]
    ]
    assert "assisted_mapping" in codes
    assert "unique_name" not in codes


def test_propose_mapping_lists_pairs_made_by_name(tmp_path: Path):
    from pythonarchtesting.mcp_server.reports import propose_mapping

    _run(tmp_path, None, _RENAMED, name_fallback=True)

    proposal = propose_mapping(str(tmp_path / "report.json"), "target")

    assert {
        "reference": "controller.handle",
        "target": "handler.handle",
        "rule": "unique_name",
    } in proposal["paired_by_name"]
    # The module itself is never paired by name: still for a mapping.
    assert "controller" in {item["reference"] for item in proposal["unpaired"]}


def test_an_entity_pair_wins_over_the_twin_of_its_module_pair(tmp_path: Path):
    handler = (
        "def handle(request, service):\n"
        "    return None\n\n\n"
        "def process(request, service):\n"
        "    return service.place(request['id'])\n"
    )
    target = _run(
        tmp_path,
        {"pairs": {"controller": "handler", "controller.handle": "handler.process"}},
        {"controller.py": None, "handler.py": handler},
    )

    match = _match(target, ":controller:handle:function:")
    assert ":handler:process:function:" in match["target_entity_id"]
    codes = [r["code"] for r in match["reasons"]]
    assert "assisted_mapping" in codes
    assert "assisted_mapping_rejected" not in codes


def test_a_targets_own_pairs_add_to_the_common_ones(tmp_path: Path):
    target = _run(
        tmp_path,
        {
            "pairs": {"controller": "handler"},
            "targets": {"target": {"pairs": {"models.Order": "models.Order"}}},
        },
        _RENAMED,
    )

    assert _status(target, "DYN011").startswith("OK")
    match = _match(target, ":controller:handle:function:")
    assert ":handler:handle:function:" in match["target_entity_id"]


def test_a_mapping_for_an_unknown_target_is_an_error(tmp_path: Path, capsys):
    import pytest

    with pytest.raises(SystemExit):
        _run(
            tmp_path,
            {"targets": {"targte": {"pairs": {"controller": "handler"}}}},
            _RENAMED,
        )
    assert "targte" in capsys.readouterr().err
