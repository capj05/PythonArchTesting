from __future__ import annotations

from pythonarchtesting.report.ir.models import ResultsSummary
from pythonarchtesting.report.ir.normalize import report_dict_to_ir
from pythonarchtesting.report.presentation.builders import (
    build_compact_passed_summary,
    build_rule_hotspots,
    build_run_presentation,
    build_target_presentation,
    group_results_by_rule,
)


def _single_report() -> dict:
    return {
        "schema_version": "2",
        "framework_version": "test",
        "generated_at": "2026-04-12T00:00:00Z",
        "exit_code": 1,
        "run": {"target_path": "/targets/alpha"},
        "matching": {
            "matches": [
                {
                    "source_entity_id": "s2",
                    "status": "unmatched",
                    "target_entity_id": None,
                    "confidence": 0.0,
                    "candidates": [],
                }
            ],
            "matching_config": {},
        },
        "results": [
            {
                "project_id": "alpha",
                "result_id": "fail-1",
                "category": "arch",
                "rule_id": "arch/rule-a",
                "rule_type": "arch/rule-a",
                "severity": "error",
                "status": "FAILED",
                "message": "Rule A failed",
                "source_entity_id": "s1",
                "target_entity_id": "t1",
                "match_status": "matched",
                "source": {
                    "module": "pkg.alpha",
                    "qualname": "Service.run",
                    "file": "alpha.py",
                    "line": 10,
                },
                "target": {
                    "module": "pkg.target",
                    "qualname": "Service.run",
                    "file": "target.py",
                    "line": 11,
                },
                "evidence": [],
                "details": {},
                "fix_hints": ["Fix A", "Shared hint"],
            },
            {
                "project_id": "alpha",
                "result_id": "warn-1",
                "category": "arch",
                "rule_id": "arch/rule-a",
                "rule_type": "arch/rule-a",
                "severity": "warning",
                "status": "WARNING",
                "message": "Rule A warning",
                "source_entity_id": "s1",
                "target_entity_id": "t1",
                "match_status": "matched",
                "source": {
                    "module": "pkg.alpha",
                    "qualname": "Service.run",
                    "file": "alpha.py",
                    "line": 10,
                },
                "target": {
                    "module": "pkg.target",
                    "qualname": "Service.run",
                    "file": "target.py",
                    "line": 11,
                },
                "evidence": [],
                "details": {},
                "fix_hints": ["Shared hint", "Fix warning"],
            },
            {
                "project_id": "alpha",
                "result_id": "skip-1",
                "category": "arch",
                "rule_id": "arch/rule-b",
                "rule_type": "arch/rule-b",
                "severity": "warning",
                "status": "SKIPPED",
                "message": "Rule B skipped",
                "source_entity_id": "s2",
                "target_entity_id": None,
                "match_status": "unmatched",
                "source": {
                    "module": "pkg.alpha",
                    "qualname": "Repository.load",
                    "file": "repo.py",
                    "line": 30,
                },
                "target": {
                    "module": None,
                    "qualname": None,
                    "file": None,
                    "line": None,
                },
                "evidence": [],
                "details": {},
                "fix_hints": ["Investigate matching"],
            },
            {
                "project_id": "alpha",
                "result_id": "ok-1",
                "category": "arch",
                "rule_id": "arch/rule-c",
                "rule_type": "arch/rule-c",
                "severity": "info",
                "status": "OK",
                "message": "Rule C ok",
                "source_entity_id": "s3",
                "target_entity_id": "t3",
                "match_status": "matched",
                "source": {
                    "module": "pkg.alpha",
                    "qualname": "Controller.handle",
                    "file": "controller.py",
                    "line": 50,
                },
                "target": {
                    "module": "pkg.target",
                    "qualname": "Controller.handle",
                    "file": "target.py",
                    "line": 50,
                },
                "evidence": [],
                "details": {},
                "fix_hints": [],
            },
            {
                "project_id": "alpha",
                "result_id": "ok-2",
                "category": "arch",
                "rule_id": "arch/rule-c",
                "rule_type": "arch/rule-c",
                "severity": "info",
                "status": "OK",
                "message": "Rule C ok again",
                "source_entity_id": "s4",
                "target_entity_id": "t4",
                "match_status": "matched",
                "source": {
                    "module": "pkg.alpha",
                    "qualname": "Controller.other",
                    "file": "controller.py",
                    "line": 55,
                },
                "target": {
                    "module": "pkg.target",
                    "qualname": "Controller.other",
                    "file": "target.py",
                    "line": 55,
                },
                "evidence": [],
                "details": {},
                "fix_hints": [],
            },
        ],
    }


def _multi_report() -> dict:
    return {
        "schema_version": "2",
        "framework_version": "test",
        "generated_at": "2026-04-12T00:00:00Z",
        "exit_code": 1,
        "run": {"source_path": "/src"},
        "summary": {
            "targets_total": 3,
            "targets_failed": 1,
            "targets_passed": 2,
            "results": {
                "results_total": 4,
                "status_counts": {"FAILED": 1, "OK": 1, "WARNING": 2},
                "severity_counts": {"error": 1, "info": 1, "warning": 2},
                "category_counts": {"arch": 4},
                "top_rules": [
                    {"name": "arch/rule-a", "count": 2},
                    {"name": "arch/rule-b", "count": 1},
                ],
                "top_source_files": [],
            },
        },
        "targets": [
            {
                "target_id": "alpha",
                "display_name": "Alpha",
                "target_path": "/targets/alpha",
                "exit_code": 1,
                "summary": {
                    "results_total": 2,
                    "status_counts": {"FAILED": 1, "WARNING": 1},
                    "severity_counts": {"error": 1, "warning": 1},
                    "category_counts": {"arch": 2},
                    "top_rules": [{"name": "arch/rule-a", "count": 2}],
                    "top_source_files": [],
                },
                "matching": {"matches": [], "matching_config": {}},
                "results": [
                    {
                        "project_id": "alpha",
                        "result_id": "a-fail",
                        "category": "arch",
                        "rule_id": "arch/rule-a",
                        "rule_type": "arch/rule-a",
                        "severity": "error",
                        "status": "FAILED",
                        "message": "Alpha fail",
                        "source_entity_id": "s1",
                        "target_entity_id": "t1",
                        "match_status": "matched",
                        "source": {
                            "module": "pkg.alpha",
                            "qualname": "Service.run",
                            "file": "alpha.py",
                            "line": 10,
                        },
                        "target": {
                            "module": "pkg.target",
                            "qualname": "Service.run",
                            "file": "target.py",
                            "line": 10,
                        },
                        "evidence": [],
                        "details": {},
                        "fix_hints": ["Fix alpha"],
                    },
                    {
                        "project_id": "alpha",
                        "result_id": "a-warn",
                        "category": "arch",
                        "rule_id": "arch/rule-a",
                        "rule_type": "arch/rule-a",
                        "severity": "warning",
                        "status": "WARNING",
                        "message": "Alpha warn",
                        "source_entity_id": "s2",
                        "target_entity_id": "t2",
                        "match_status": "matched",
                        "source": {
                            "module": "pkg.alpha",
                            "qualname": "Service.warn",
                            "file": "alpha.py",
                            "line": 12,
                        },
                        "target": {
                            "module": "pkg.target",
                            "qualname": "Service.warn",
                            "file": "target.py",
                            "line": 12,
                        },
                        "evidence": [],
                        "details": {},
                        "fix_hints": [],
                    },
                ],
            },
            {
                "target_id": "beta",
                "display_name": "Beta",
                "target_path": "/targets/beta",
                "exit_code": 0,
                "summary": {
                    "results_total": 1,
                    "status_counts": {"WARNING": 1},
                    "severity_counts": {"warning": 1},
                    "category_counts": {"arch": 1},
                    "top_rules": [{"name": "arch/rule-b", "count": 1}],
                    "top_source_files": [],
                },
                "matching": {"matches": [], "matching_config": {}},
                "results": [
                    {
                        "project_id": "beta",
                        "result_id": "b-warn",
                        "category": "arch",
                        "rule_id": "arch/rule-b",
                        "rule_type": "arch/rule-b",
                        "severity": "warning",
                        "status": "WARNING",
                        "message": "Beta warn",
                        "source_entity_id": "s3",
                        "target_entity_id": "t3",
                        "match_status": "matched",
                        "source": {
                            "module": "pkg.beta",
                            "qualname": "Service.warn",
                            "file": "beta.py",
                            "line": 20,
                        },
                        "target": {
                            "module": "pkg.target",
                            "qualname": "Service.warn",
                            "file": "target.py",
                            "line": 20,
                        },
                        "evidence": [],
                        "details": {},
                        "fix_hints": [],
                    }
                ],
            },
            {
                "target_id": "gamma",
                "display_name": "Gamma",
                "target_path": "/targets/gamma",
                "exit_code": 0,
                "summary": {
                    "results_total": 1,
                    "status_counts": {"OK": 1},
                    "severity_counts": {"info": 1},
                    "category_counts": {"arch": 1},
                    "top_rules": [{"name": "arch/rule-c", "count": 1}],
                    "top_source_files": [],
                },
                "matching": {"matches": [], "matching_config": {}},
                "results": [
                    {
                        "project_id": "gamma",
                        "result_id": "g-ok",
                        "category": "arch",
                        "rule_id": "arch/rule-c",
                        "rule_type": "arch/rule-c",
                        "severity": "info",
                        "status": "OK",
                        "message": "Gamma ok",
                        "source_entity_id": "s4",
                        "target_entity_id": "t4",
                        "match_status": "matched",
                        "source": {
                            "module": "pkg.gamma",
                            "qualname": "Service.ok",
                            "file": "gamma.py",
                            "line": 30,
                        },
                        "target": {
                            "module": "pkg.target",
                            "qualname": "Service.ok",
                            "file": "target.py",
                            "line": 30,
                        },
                        "evidence": [],
                        "details": {},
                        "fix_hints": [],
                    }
                ],
            },
        ],
    }


def test_group_results_by_rule_dedupes_hints_and_preserves_warning_rows() -> None:
    document = report_dict_to_ir(_single_report(), kind="single")
    groups = group_results_by_rule(document.targets[0].results, mode="verbose")

    assert [group.rule_id for group in groups] == ["arch/rule-a", "arch/rule-b"]
    assert groups[0].display_status == "ISSUES"
    assert groups[0].failed_count == 1
    assert groups[0].warning_count == 1
    assert groups[0].fix_hints == ("Fix A", "Shared hint", "Fix warning")
    assert groups[1].display_status == "WARNINGS ONLY"
    assert groups[1].show_matching_context is True


def test_build_target_presentation_from_ir_uses_contextual_matching() -> None:
    document = report_dict_to_ir(_single_report(), kind="single")
    presentation = build_target_presentation(document.targets[0], mode="verbose")

    assert presentation.display_status == "ISSUES"
    assert [group.rule_id for group in presentation.issue_groups] == ["arch/rule-a"]
    assert [group.rule_id for group in presentation.warning_groups] == ["arch/rule-b"]
    assert presentation.matching_summary.visibility == "contextual"
    assert presentation.compact_passed_summary.passed_total == 2
    assert (
        presentation.compact_passed_summary.top_passed_rules[0].rule_id == "arch/rule-c"
    )
    assert presentation.compact_passed_summary.hidden_passed_count == 0


def test_build_run_presentation_from_multi_ir_groups_targets() -> None:
    document = report_dict_to_ir(_multi_report(), kind="multi")
    presentation = build_run_presentation(document, mode="verbose")

    assert presentation.display_status == "ISSUES"
    assert presentation.targets_total == 3
    assert presentation.targets_issues == 1
    assert presentation.targets_warnings_only == 1
    assert presentation.targets_ok == 1
    assert presentation.has_target_pages is True
    assert [card.target_id for card in presentation.targets_with_issues] == ["alpha"]
    assert [card.target_id for card in presentation.warnings_only_targets] == ["beta"]
    assert [card.target_id for card in presentation.ok_targets] == ["gamma"]
    assert [hotspot.rule_id for hotspot in presentation.rule_hotspots] == [
        "arch/rule-a",
        "arch/rule-b",
    ]
    assert presentation.rule_hotspots[0].targets_affected == 1


def test_build_rule_hotspots_falls_back_when_summary_is_empty() -> None:
    document = report_dict_to_ir(_multi_report(), kind="multi")
    empty_summary = ResultsSummary(
        results_total=document.summary.results.results_total,
        status_counts=document.summary.results.status_counts,
        severity_counts=document.summary.results.severity_counts,
        category_counts=document.summary.results.category_counts,
        top_rules=tuple(),
        top_source_files=document.summary.results.top_source_files,
        timings=document.summary.results.timings,
    )

    hotspots = build_rule_hotspots(empty_summary, document.targets)

    assert [hotspot.rule_id for hotspot in hotspots[:3]] == [
        "arch/rule-a",
        "arch/rule-b",
        "arch/rule-c",
    ]
    assert hotspots[0].count == 2


def test_build_compact_passed_summary_uses_top_three_rules() -> None:
    document = report_dict_to_ir(
        {
            "schema_version": "2",
            "framework_version": "test",
            "generated_at": "2026-04-12T00:00:00Z",
            "exit_code": 0,
            "run": {"target_path": "/targets/ok"},
            "matching": {"matches": []},
            "results": [
                {
                    "project_id": "ok",
                    "result_id": f"ok-{idx}",
                    "category": "arch",
                    "rule_id": rule_id,
                    "rule_type": rule_id,
                    "severity": "info",
                    "status": "OK",
                    "message": "ok",
                    "source_entity_id": f"s-{idx}",
                    "target_entity_id": f"t-{idx}",
                    "match_status": "matched",
                    "source": {
                        "module": "pkg",
                        "qualname": f"Fn{idx}",
                        "file": "a.py",
                        "line": idx,
                    },
                    "target": {
                        "module": "pkg",
                        "qualname": f"Fn{idx}",
                        "file": "b.py",
                        "line": idx,
                    },
                    "evidence": [],
                    "details": {},
                    "fix_hints": [],
                }
                for idx, rule_id in enumerate(
                    ["rule/a", "rule/a", "rule/b", "rule/c", "rule/d"],
                    start=1,
                )
            ],
        },
        kind="single",
    )

    summary = build_compact_passed_summary(document.targets[0].results)

    assert summary.passed_total == 5
    assert [item.rule_id for item in summary.top_passed_rules] == [
        "rule/a",
        "rule/b",
        "rule/c",
    ]
    assert summary.hidden_passed_count == 1
