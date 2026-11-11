from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.cli import main
from pythonarchtesting.mcp_server.errors import ToolInputError
from pythonarchtesting.mcp_server.reports import (
    explain_rule,
    explain_target,
    propose_mapping,
    summarize_report,
)

MUTANTS_DIR = Path(__file__).parents[3] / "example" / "architectural_mutants"


def _mutant(mutant_id: str) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location(
        "_arch_mutants", MUTANTS_DIR / "mutants.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return next(m for m in module.MUTANTS if m["id"] == mutant_id)


@pytest.fixture(scope="module")
def report_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("reports")
    mutated = root / "mutated"
    shutil.copytree(MUTANTS_DIR / "solution", mutated)
    for name, old, new in _mutant("M02")["patches"]:
        path = mutated / name
        path.write_text(
            path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8"
        )
    output = root / "report.json"
    main(
        [
            "--source",
            str(MUTANTS_DIR / "reference"),
            "--target",
            str(MUTANTS_DIR / "solution"),
            "--target",
            str(mutated),
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )
    return output


def _failing_target(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    return next(t for t in report["targets"] if t["exit_code"] != 0)


def test_summarize_counts(report_path: Path):
    summary = summarize_report(str(report_path))
    assert summary["targets_total"] == 2
    assert summary["targets_failed"] == 1
    top = summary["rules"][0]
    assert top["rule"].startswith("DEP001/forbid_imports/v2@")
    assert top["failing_targets"] == 1


def test_explain_target_lists_problems_only(report_path: Path):
    target = _failing_target(report_path)
    explained = explain_target(str(report_path), target["target_id"])
    assert explained["results"]
    for item in explained["results"]:
        assert item["status"] in ("FAILED", "ERROR")
        assert item["fix_hints"]


def test_explain_target_caps_evidence(report_path: Path, tmp_path: Path):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    target = next(t for t in report["targets"] if t["exit_code"] != 0)
    failed = next(r for r in target["results"] if r["status"] == "FAILED")
    failed["evidence"] = [{"n": i} for i in range(12)]
    path = tmp_path / "many.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    explained = explain_target(str(path), target["target_id"])
    item = next(i for i in explained["results"] if i["evidence_total"] == 12)
    assert len(item["evidence"]) == 5


def test_unknown_target_and_rule_raise(report_path: Path):
    with pytest.raises(ToolInputError, match="2 targets"):
        explain_target(str(report_path), "nope")
    with pytest.raises(ToolInputError, match=r"\d+ rules"):
        explain_rule(str(report_path), "nope")


def test_explain_rule_lists_problems_first(report_path: Path):
    key = summarize_report(str(report_path))["rules"][0]["rule"]
    explained = explain_rule(str(report_path), key)
    assert explained["targets"][0]["status"] == "FAILED"
    assert explained["counts"]["FAILED"] == 1
    assert explained["counts"]["OK"] == 1


def test_non_v2_json_rejected(tmp_path: Path):
    path = tmp_path / "old.json"
    path.write_text('{"mode": "validate-declarations"}', encoding="utf-8")
    with pytest.raises(ToolInputError):
        summarize_report(str(path))


def test_relative_and_missing_paths_rejected(tmp_path: Path):
    with pytest.raises(ToolInputError, match="absolute"):
        summarize_report("report.json")
    with pytest.raises(ToolInputError, match="does not exist"):
        summarize_report(str(tmp_path / "missing.json"))
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(ToolInputError, match="not valid JSON"):
        summarize_report(str(broken))


def test_paging_limits(report_path: Path):
    summary = summarize_report(str(report_path), limit=1)
    assert len(summary["targets"]) == 1
    assert summary["targets_page_total"] == 2
    assert summary["limit"] == 1
    assert summarize_report(str(report_path), limit=0)["limit"] == 1
    assert summarize_report(str(report_path), limit=999)["limit"] == 200


def test_malformed_report_raises_tool_input_error(report_path: Path, tmp_path: Path):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    target = next(t for t in report["targets"] if t["exit_code"] != 0)
    del next(r for r in target["results"] if r["status"] == "FAILED")["locations"]
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ToolInputError, match="malformed report"):
        summarize_report(str(path))
    with pytest.raises(ToolInputError, match="malformed report"):
        explain_target(str(path), target["target_id"])
    with pytest.raises(ToolInputError, match="malformed report"):
        explain_rule(str(path), "anything")


def test_malformed_entity_id_raises_tool_input_error(report_path: Path, tmp_path: Path):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    target = report["targets"][0]
    match = target["matching"]["matches"][0]
    match["status"], match["source_entity_id"] = "unmatched", "a:b"
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ToolInputError, match="malformed report.*canonical entity id"):
        propose_mapping(str(path), target["target_id"])
    # the wrapper passes the tools' own refusals on unchanged
    with pytest.raises(ToolInputError, match="^unknown target|2 targets"):
        propose_mapping(str(path), "nope")
