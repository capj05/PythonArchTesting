"""The MCP tools that read a report by the typical errors of a principle."""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any, Optional

import anyio
import pytest

from pythonarchtesting.mcp_server.errors import ToolInputError
from pythonarchtesting.mcp_server.reports import (
    class_overview,
    explain_target,
    summarize_report,
)

_WRITES = "DYN003/forbid_foreign_writes/v1"
_HINTS = [
    "Ask the object to change itself through one of its methods instead of "
    "assigning its attribute from outside.",
    "Runs only with --dynamic; without it the rule is SKIPPED.",
]


def _write(attribute: str, change: str, line: int, writer: str) -> dict[str, Any]:
    return {
        "attribute": attribute,
        "case": 0,
        "change": change,
        "class": "Inventory",
        "file": "shop.py",
        "kind": "write",
        "line": line,
        "writer": writer,
    }


def _location(qualname: str, line: int) -> dict[str, Any]:
    return {"file": "shop.py", "line": line, "module": "shop", "qualname": qualname}


def _result(
    name: str,
    qualname: str,
    facts: Optional[list[dict[str, Any]]],
    status: str = "FAILED",
    rule_id: str = _WRITES,
    reason: str = "violation",
) -> dict[str, Any]:
    texts = [
        f"case 0: shop:{qualname} writes Inventory.{f['attribute']} at shop.py:{f['line']}"
        for f in facts or []
    ]
    details: dict[str, Any] = {"reason": reason, "probe_status": "completed"}
    if facts is not None:
        details.update({"facts": facts, "violations": texts, "summary": texts[0]})
    message = f"{rule_id.split('/')[1]} for shop:{qualname}: " + (
        texts[0] if texts else f"{reason} while checking"
    )
    return {
        "result_id": f"{name}:{rule_id}:{qualname}",
        "project_id": name,
        "rule_id": rule_id,
        "category": "runtime_writes",
        "severity": "error",
        "status": status,
        "source": _location(qualname, 40),
        "target": _location(qualname, 8),
        "message": message if status != "OK" else "ok",
        "evidence": [],
        "fix_hints": list(_HINTS),
        "locations": {
            "source": {**_location(qualname, 40), "class": None, "function": qualname},
            "target": {**_location(qualname, 8), "class": None, "function": qualname},
        },
        "details": details,
    }


def _unmatched(name: str, qualname: str) -> dict[str, Any]:
    """As a real report gives a reference entity without a counterpart: the
    target dicts exist, with every field ``None``."""
    result = _result(name, qualname, None, reason="required_target_missing")
    empty = {"file": None, "line": None, "module": None, "qualname": None}
    result["target"] = dict(empty)
    result["locations"]["target"] = {**empty, "class": None, "function": None}
    result["details"] = {
        "confidence": 0.0,
        "match_status": "unmatched",
        "reason": "required_target_missing",
    }
    result["message"] = (
        "Required target entity missing or not matchable "
        "(status=unmatched, confidence=0.0)."
    )
    return result


def _skipped(name: str, qualname: str) -> dict[str, Any]:
    return _result(
        name, qualname, None, status="SKIPPED", reason="dynamic_checks_disabled"
    )


def _target(name: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    failed = any(r["status"] not in ("OK", "SKIPPED") for r in results)
    return {
        "target_id": name,
        "display_name": name,
        "target_path": f"/class/{name}",
        "exit_code": 1 if failed else 0,
        "matching": {"matches": []},
        "results": results,
    }


def _report(path: Path, targets: list[dict[str, Any]]) -> Path:
    report = {
        "schema_version": "2",
        "generated_at": "2026-11-05T00:00:00Z",
        "exit_code": 1 if any(t["exit_code"] for t in targets) else 0,
        "run": {"mode": "dynamic (sandbox: bwrap)", "source_path": "/reference"},
        "targets": targets,
    }
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


@pytest.fixture
def report_path(tmp_path: Path) -> Path:
    targets = [
        _target("xxxx01_novak", [_result("xxxx01_novak", "sell", None, status="OK")]),
        _target(
            "xxxx02_dvorak",
            [
                _result(
                    "xxxx02_dvorak",
                    "sell",
                    [_write("_stock", "mutated", 10, "shop:sell")],
                )
            ],
        ),
        _target(
            "xxxx03_svoboda",
            [
                _result(
                    "xxxx03_svoboda",
                    "restock",
                    [
                        _write("log", "mutated", 15, "shop:restock"),
                        _write("_stock", "mutated", 16, "shop:restock"),
                    ],
                )
            ],
        ),
        # A deleted attribute: no catalogue error declares it (Review Focus 2).
        _target(
            "xxxx04_cerna",
            [
                _result(
                    "xxxx04_cerna",
                    "clear_out",
                    [_write("_stock", "deleted", 19, "shop:clear_out")],
                )
            ],
        ),
        # The matching found no counterpart of the reference's sell.
        _target("xxxx05_kral", [_unmatched("xxxx05_kral", "sell")]),
        # The probe could not import the submission.
        _target(
            "xxxx06_benes",
            [_result("xxxx06_benes", "sell", None, reason="probe_import_error")],
        ),
        # A static run: the runtime check was SKIPPED, so nothing was judged.
        _target("xxxx07_horak", [_skipped("xxxx07_horak", "sell")]),
        # A violation in sell, and restock without a counterpart.
        _target(
            "xxxx08_ruzicka",
            [
                _result(
                    "xxxx08_ruzicka",
                    "sell",
                    [_write("_stock", "mutated", 10, "shop:sell")],
                ),
                _unmatched("xxxx08_ruzicka", "restock"),
            ],
        ),
    ]
    return _report(tmp_path / "report.json", targets)


def test_class_overview_counts_by_error(report_path: Path):
    overview = class_overview(str(report_path), "encapsulation")

    assert overview["principle"] == "encapsulation"
    counts = (
        overview["submissions"],
        overview["passed"],
        overview["failed"],
        overview["not_judged"],
    )
    assert counts == (8, 1, 5, 2)
    assert sum(counts[1:]) == counts[0]
    by_error = overview["by_error"]
    assert list(by_error) == [
        "bypass_method",
        "mutate_container",
        "missing_required_entity",
        "unclassified",
    ]
    assert by_error["bypass_method"]["count"] == 3
    assert by_error["bypass_method"]["submissions_total"] == 3
    assert by_error["bypass_method"]["submissions"] == [
        "xxxx02_dvorak",
        "xxxx03_svoboda",
        "xxxx08_ruzicka",
    ]
    assert by_error["mutate_container"]["submissions"] == ["xxxx03_svoboda"]
    # Only a genuine violation that no typical error explains.
    assert by_error["unclassified"]["submissions"] == ["xxxx04_cerna"]
    # A reference entity without a counterpart: the tool's own error.
    assert by_error["missing_required_entity"]["submissions"] == [
        "xxxx05_kral",
        "xxxx08_ruzicka",
    ]
    assert by_error["missing_required_entity"]["title"]
    assert by_error["bypass_method"]["title"]
    assert "title" not in by_error["unclassified"]
    assert overview["not_judged_by_reason"] == {
        "probe_import_error": {
            "count": 1,
            "submissions": ["xxxx06_benes"],
            "submissions_total": 1,
        },
        "dynamic_checks_disabled": {
            "count": 1,
            "submissions": ["xxxx07_horak"],
            "submissions_total": 1,
        },
    }
    rows = {row["name"]: row for row in overview["submissions_page"]}
    assert {name: row["verdict"] for name, row in rows.items()} == {
        "xxxx01_novak": "passed",
        "xxxx02_dvorak": "failed",
        "xxxx03_svoboda": "failed",
        "xxxx04_cerna": "failed",
        "xxxx05_kral": "failed",
        "xxxx06_benes": "not_judged",
        "xxxx07_horak": "not_judged",
        "xxxx08_ruzicka": "failed",
    }
    assert {name: row["errors"] for name, row in rows.items()} == {
        "xxxx01_novak": [],
        "xxxx02_dvorak": ["bypass_method"],
        "xxxx03_svoboda": ["mutate_container", "bypass_method"],
        "xxxx04_cerna": ["unclassified"],
        "xxxx05_kral": ["missing_required_entity"],
        "xxxx06_benes": [],
        "xxxx07_horak": [],
        "xxxx08_ruzicka": ["bypass_method", "missing_required_entity"],
    }
    assert "not_judged" not in rows["xxxx08_ruzicka"]
    assert "not_judged" not in rows["xxxx05_kral"]
    assert "not_judged" not in rows["xxxx02_dvorak"]


def test_a_static_run_judges_nobody(report_path: Path, tmp_path: Path):
    """C1: without dynamic the runtime checks are SKIPPED; nobody passes."""
    names = [f"xxxx{i:02d}_student" for i in range(3)]
    path = _report(
        tmp_path / "static.json",
        [_target(n, [_skipped(n, "sell"), _skipped(n, "restock")]) for n in names],
    )

    overview = class_overview(str(path), "encapsulation")
    summary = summarize_report(str(path), principle="encapsulation")

    assert (overview["passed"], overview["failed"], overview["not_judged"]) == (0, 0, 3)
    assert overview["not_judged_by_reason"]["dynamic_checks_disabled"]["count"] == 3
    assert (summary["passed"], summary["failed"], summary["not_judged"]) == (0, 0, 3)
    assert {t["verdict"] for t in summary["targets"]} == {"not_judged"}


def test_a_report_without_the_principles_checks_judges_nobody(tmp_path: Path):
    calls = "DYN001/forbid_runtime_calls/v1"
    path = _report(
        tmp_path / "other.json",
        [
            _target(
                "xxxx01_novak",
                [_result("xxxx01_novak", "sell", None, status="OK", rule_id=calls)],
            )
        ],
    )

    overview = class_overview(str(path), "encapsulation")

    assert overview["not_judged"] == 1
    assert list(overview["not_judged_by_reason"]) == ["no_principle_checks"]


def test_long_submission_lists_are_capped(tmp_path: Path):
    targets = []
    for index in range(60):
        name = f"xxxx{index:02d}_student"
        facts = [_write("_stock", "mutated", 10, "shop:sell")]
        targets.append(_target(name, [_result(name, "sell", facts)]))
    path = _report(tmp_path / "report.json", targets)

    bucket = class_overview(str(path), "encapsulation")["by_error"]["bypass_method"]

    assert (bucket["count"], bucket["submissions_total"]) == (60, 60)
    assert len(bucket["submissions"]) == 50


def test_class_overview_pages_the_submissions(report_path: Path):
    overview = class_overview(str(report_path), "encapsulation", offset=1, limit=2)

    assert [row["name"] for row in overview["submissions_page"]] == [
        "xxxx02_dvorak",
        "xxxx03_svoboda",
    ]
    assert (overview["offset"], overview["limit"]) == (1, 2)
    # The counts cover the whole class, not the page.
    assert overview["by_error"]["bypass_method"]["count"] == 3


def test_unclassified_violation_does_not_disappear(report_path: Path):
    found = explain_target(str(report_path), "xxxx04_cerna", principle="encapsulation")

    [finding] = found["findings"]
    assert finding["error_id"] is None
    assert finding["facts"]["change"] == "deleted"
    assert "Inventory._stock" in finding["text"]


def test_explain_target_with_principle_gives_findings(report_path: Path):
    found = explain_target(
        str(report_path), "xxxx03_svoboda", principle="encapsulation"
    )

    assert "results" not in found
    assert found["principle"] == "encapsulation"
    assert found["verdict"] == "failed"
    assert found["findings_total"] == 2
    first, second = found["findings"]
    assert first["error_id"] == "mutate_container"
    assert second["error_id"] == "bypass_method"
    assert first["what"].startswith("Function `restock` (shop.py:8)")
    assert {"rule", "target", "facts"} <= set(first)
    # m2: title, why and fix once per error, not per finding; ``what`` states
    # what the report's text says.
    assert {"title", "why", "fix", "text"}.isdisjoint(first)
    assert set(found["errors"]) == {"mutate_container", "bypass_method"}
    assert set(found["errors"]["bypass_method"]) == {"title", "why", "fix"}
    assert first["target"] == "shop:restock"


def test_explain_target_with_principle_honours_include_passed(report_path: Path):
    plain = explain_target(str(report_path), "xxxx01_novak", principle="encapsulation")
    passed = explain_target(
        str(report_path), "xxxx01_novak", principle="encapsulation", include_passed=True
    )

    assert plain["verdict"] == "passed" and "passed" not in plain
    assert passed["passed"] == [
        {"rule": "DYN003/forbid_foreign_writes/v1", "target": "shop:sell"}
    ]


def test_explain_target_without_principle_is_unchanged(report_path: Path):
    found = explain_target(str(report_path), "xxxx03_svoboda")

    assert "findings" not in found and "principle" not in found
    assert found["results_total"] == 1
    assert found["results"][0]["feedback"]["issues"][0]["attribute"] == "log"


def test_explain_target_names_the_missing_entity(report_path: Path):
    found = explain_target(str(report_path), "xxxx05_kral", principle="encapsulation")

    assert found["verdict"] == "failed"
    [finding] = found["findings"]
    assert finding["error_id"] == "missing_required_entity"
    assert "not_judged" not in finding
    assert finding["target"] == "shop:sell"
    assert finding["rule"] == _WRITES
    assert finding["facts"]["entity"] == "shop.sell"
    assert (finding["facts"]["file"], finding["facts"]["line"]) == ("shop.py", 40)
    assert "`shop.sell`" in finding["what"]
    assert set(found["errors"]) == {"missing_required_entity"}
    assert set(found["errors"]["missing_required_entity"]) == {"title", "why", "fix"}


def test_explain_target_of_a_skipped_submission(report_path: Path):
    found = explain_target(str(report_path), "xxxx07_horak", principle="encapsulation")

    assert found["verdict"] == "not_judged"
    assert found["not_judged"] == ["dynamic_checks_disabled"]
    assert found["findings"] == []


def test_summarize_report_with_principle(report_path: Path):
    plain = summarize_report(str(report_path))
    summary = summarize_report(str(report_path), principle="encapsulation")

    assert "by_error" not in plain and "not_judged" not in plain
    assert summary["principle"] == "encapsulation"
    assert summary["by_error"] == {
        "bypass_method": 3,
        "mutate_container": 1,
        "missing_required_entity": 2,
        "unclassified": 1,
    }
    assert summary["not_judged_by_reason"] == {
        "probe_import_error": 1,
        "dynamic_checks_disabled": 1,
    }
    assert (summary["passed"], summary["failed"], summary["not_judged"]) == (1, 5, 2)
    rows = {t["target_id"]: t for t in summary["targets"]}
    assert rows["xxxx03_svoboda"]["errors"] == ["mutate_container", "bypass_method"]
    assert rows["xxxx01_novak"]["errors"] == []
    assert rows["xxxx01_novak"]["verdict"] == "passed"
    assert rows["xxxx06_benes"]["verdict"] == "not_judged"
    assert rows["xxxx06_benes"]["not_judged"] == ["probe_import_error"]


def test_unknown_principle_is_a_tool_input_error(report_path: Path):
    with pytest.raises(ToolInputError, match="did you mean: encapsulation"):
        class_overview(str(report_path), "encapsulaton")
    with pytest.raises(ToolInputError, match="unknown principle"):
        explain_target(str(report_path), "xxxx01_novak", principle="nope")


def test_a_principle_other_than_the_recorded_one_is_a_tool_input_error(
    report_path: Path,
):
    """Audit K4: a report that records its principle (a run whose source was
    a task) is not read by another one, as run_evaluation refuses it too."""
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["run"]["principle"] = "encapsulation"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    path = str(report_path)

    with pytest.raises(ToolInputError, match="records the principle 'encapsulation'"):
        class_overview(path, "polymorphism")
    with pytest.raises(ToolInputError, match="records the principle 'encapsulation'"):
        explain_target(path, "xxxx01_novak", principle="polymorphism")
    with pytest.raises(ToolInputError, match="records the principle 'encapsulation'"):
        summarize_report(path, principle="polymorphism")
    # The recorded one, given or implied, still reads the report.
    assert class_overview(path)["principle"] == "encapsulation"
    assert class_overview(path, "encapsulation")["principle"] == "encapsulation"
    found = explain_target(path, "xxxx01_novak", principle="encapsulation")
    assert found["principle"] == "encapsulation"
    assert summarize_report(path, principle="encapsulation")["principle"] == (
        "encapsulation"
    )


def _student(index: int) -> dict[str, Any]:
    """Submission ``index`` of a realistic class: three rules with up to three
    facts each, mixing typical errors, unclassified violations, an unmatched
    entity and submissions the probe could not import."""
    name = f"xxxx{index:02d}_student{index:02d}"
    if index % 10 == 7:
        return _target(
            name,
            [
                _result(name, qualname, None, reason="probe_import_error")
                for qualname in ("sell", "restock", "clear_out")
            ],
        )
    changes = ["mutated", "assigned", "deleted"]
    results = []
    for rule, qualname in enumerate(("sell", "restock", "clear_out")):
        if index % 6 == 5 and qualname == "clear_out":
            results.append(_unmatched(name, qualname))
            continue
        count = 3 if index % 4 == 0 else (index + rule) % 4  # 0..3 facts
        facts = [
            _write(
                "_stock" if n % 2 == 0 else "log",
                changes[(index + n) % 3],
                10 + n,
                f"shop:{qualname}",
            )
            for n in range(count)
        ]
        status = "FAILED" if facts else "OK"
        results.append(_result(name, qualname, facts or None, status=status))
    return _target(name, results)


def test_class_of_30_stays_small(tmp_path: Path):
    """Review Focus 3: 30 submissions x 3 rules x up to 3 facts."""
    targets = [_student(index) for index in range(30)]
    path = _report(tmp_path / "report.json", targets)

    overview = class_overview(str(path), "encapsulation")
    summary = summarize_report(str(path), principle="encapsulation")
    busiest = max(
        targets,
        key=lambda t: sum(len((r["details"].get("facts") or [])) for r in t["results"]),
    )
    one = explain_target(str(path), busiest["target_id"], principle="encapsulation")

    assert overview["submissions"] == 30
    assert overview["not_judged"] >= 3
    assert "unclassified" in overview["by_error"]
    assert "missing_required_entity" in overview["by_error"]
    assert overview["passed"] + overview["failed"] + overview["not_judged"] == 30
    assert len(overview["submissions_page"]) == 30
    assert len(json.dumps(overview).encode("utf-8")) <= 20_000
    assert len(json.dumps(summary).encode("utf-8")) <= 20_000
    assert one["findings_total"] == 9
    sizes = {
        "class_overview": len(json.dumps(overview).encode("utf-8")),
        "summarize_report": len(json.dumps(summary).encode("utf-8")),
        "explain_target": len(json.dumps(one).encode("utf-8")),
    }
    print(sizes)
    assert sizes["class_overview"] <= 20_000
    assert sizes["summarize_report"] <= 20_000
    assert sizes["explain_target"] <= 4_000


def test_class_overview_through_the_server(report_path: Path):
    pytest.importorskip("mcp")
    from mcp.server.mcpserver.exceptions import ToolError

    from pythonarchtesting.mcp_server import server

    async def call(name: str, arguments: dict[str, Any]) -> Any:
        return await server.mcp.call_tool(name, arguments)

    path = str(report_path)
    overview = anyio.run(
        call, "class_overview", {"report_path": path, "principle": "encapsulation"}
    )
    assert "xxxx02_dvorak" in str(overview)
    explained = anyio.run(
        call,
        "explain_target",
        {"report_path": path, "target": "xxxx02_dvorak", "principle": "encapsulation"},
    )
    assert "bypass_method" in str(explained)
    summary = anyio.run(
        call, "summarize_report", {"report_path": path, "principle": "encapsulation"}
    )
    assert "by_error" in str(summary)
    with pytest.raises(ToolError, match="unknown principle"):
        anyio.run(call, "class_overview", {"report_path": path, "principle": "nope"})


class _Context:
    """Stands in for the request context: progress goes nowhere."""

    async def report_progress(self, *args: Any) -> None:
        return None


def test_run_evaluation_echoes_the_principle(tmp_path: Path):
    pytest.importorskip("mcp")
    from mcp.server.mcpserver.exceptions import ToolError

    from pythonarchtesting.mcp_server import server

    mutants = Path(__file__).parents[3] / "example" / "architectural_mutants"

    async def call(
        output_dir: Path, principle: Optional[str], **extra: Any
    ) -> dict[str, Any]:
        return await server.run_evaluation(
            _Context(),  # type: ignore[arg-type]
            source=str(mutants / "reference"),
            output_dir=str(output_dir),
            targets=[str(mutants / "solution")],
            principle=principle,
            **extra,
        )

    result = anyio.run(call, tmp_path / "out", "encapsulation")
    assert result["principle"] == "encapsulation"
    assert result["targets_total"] == 1
    # C1: a principle's checks run the code; without dynamic they would be
    # SKIPPED and every submission would look like it passed.
    assert result["dynamic_forced"] is True
    assert result["mode"].startswith("dynamic")
    explicit = anyio.run(
        functools.partial(call, tmp_path / "explicit", "encapsulation", dynamic=True)
    )
    assert explicit["dynamic_forced"] is False
    plain = anyio.run(call, tmp_path / "plain", None)
    assert "principle" not in plain and "dynamic_forced" not in plain
    assert not plain["mode"].startswith("dynamic")
    bad = tmp_path / "bad"
    with pytest.raises(ToolError, match="unknown principle"):
        anyio.run(call, bad, "nope")
    assert not bad.exists()
    static = tmp_path / "static"
    with pytest.raises(ToolError, match="needs a dynamic run"):
        anyio.run(functools.partial(call, static, "encapsulation", dynamic=False))
    assert not static.exists()
