from __future__ import annotations

from pathlib import Path

import pytest

from pythonarchtesting.report.ir.models import (
    AggregateSummary,
    MatchingSection,
    ReportDocument,
    RunMeta,
    TargetReport,
)
from pythonarchtesting.report.ir.normalize import matching_summary, results_summary
from pythonarchtesting.report.renderers.markdown_bundle import render_markdown_bundle
from pythonarchtesting.report.renderers.matching_debug import (
    build_matching_debug_blocks_for_target,
    collect_metric_columns,
    compute_metric_normalization,
)


def _single_report_with_matching() -> dict:
    return {
        "schema_version": "2",
        "framework_version": "test",
        "generated_at": "2026-02-22T00:00:00Z",
        "exit_code": 0,
        "run": {"target_path": "/target"},
        "summary": {
            "results_total": 0,
            "severity_counts": {},
            "status_counts": {},
            "category_counts": {},
        },
        "matching": {
            "matches": [
                {
                    "source_entity_id": "s.alpha",
                    "status": "matched",
                    "target_entity_id": "t.selected",
                    "confidence": 0.912345,
                    "candidates": [
                        {
                            "target_entity_id": "t.b",
                            "confidence": 0.7,
                            "breakdown": {
                                "mod": 0.8,
                                "ast": 0.6,
                                "module_distance": 2.0,
                            },
                            "explanations": "runner up\nline2",
                        },
                        {
                            "target_entity_id": "t.selected",
                            "confidence": 0.912345,
                            "breakdown": {
                                "mod": 1.0,
                                "ast": 0.9,
                                "module_distance": 0.0,
                                "custom_metric": 42.0,
                            },
                            "explanations": {"overall": "best <candidate>"},
                        },
                        {
                            "target_entity_id": "t.a",
                            "confidence": 0.7,
                            "breakdown": {
                                "mod": 0.8,
                                "ast": 0.6,
                                "module_distance": 1.0,
                            },
                        },
                    ],
                },
                {
                    "source_entity_id": "s.none",
                    "status": "unmatched",
                    "target_entity_id": None,
                    "confidence": 0.0,
                    "candidates": [],
                },
            ],
            "matching_config": {},
        },
        "results": [],
    }


def _single_context() -> dict:
    return {
        "kind": "single",
        "targets": {
            "__single__": {
                "sources": {
                    "s.alpha": {
                        "id": "s.alpha",
                        "name": "Src <A>|`tick`",
                        "type": "method",
                        "location": "src/a.py:10",
                    },
                    "s.none": {
                        "id": "s.none",
                        "name": "NoCandidates",
                        "type": "function",
                        "location": "src/none.py:1",
                    },
                },
                "targets": {
                    "t.selected": {
                        "id": "t.selected",
                        "name": 'Target "Sel"',
                        "type": "method",
                        "location": "tgt/sel.py:5",
                    },
                    "t.a": {
                        "id": "t.a",
                        "name": "Target A",
                        "type": "method",
                        "location": "tgt/a.py:2",
                    },
                    "t.b": {
                        "id": "t.b",
                        "name": "Target B",
                        "type": "method",
                        "location": "tgt/b.py:3",
                    },
                },
            }
        },
    }


def _single_target_wrapper(report: dict) -> dict:
    return {
        "display_name": "__single__",
        "target_id": "__single__",
        "target_path": "/target",
        "matching": report["matching"],
    }


def test_matching_debug_source_blocks_include_matched_unmatched_and_no_candidates():
    report = _single_report_with_matching()
    ctx = _single_context()["targets"]["__single__"]

    blocks = build_matching_debug_blocks_for_target(
        _single_target_wrapper(report), ctx, top_k=10
    )

    assert [b.source.id for b in blocks] == ["s.none", "s.alpha"]
    alpha = next(b for b in blocks if b.source.id == "s.alpha")
    none_block = next(b for b in blocks if b.source.id == "s.none")
    assert alpha.match_status == "matched"
    assert alpha.matched_target is not None
    assert alpha.matched_target.id == "t.selected"
    assert alpha.candidates_total == 3
    assert none_block.match_status == "unmatched"
    assert none_block.candidates_total == 0


def test_matching_debug_candidate_sorting_confidence_then_id_then_name():
    report = _single_report_with_matching()
    ctx = _single_context()["targets"]["__single__"]
    blocks = build_matching_debug_blocks_for_target(
        _single_target_wrapper(report), ctx, top_k=10
    )
    alpha = next(b for b in blocks if b.source.id == "s.alpha")

    assert [c.target.id for c in alpha.candidates_shown] == ["t.selected", "t.a", "t.b"]


def test_matching_debug_truncates_candidates_and_reports_hidden_count():
    report = _single_report_with_matching()
    ctx = _single_context()["targets"]["__single__"]
    blocks = build_matching_debug_blocks_for_target(
        _single_target_wrapper(report), ctx, top_k=2
    )
    alpha = next(b for b in blocks if b.source.id == "s.alpha")

    assert len(alpha.candidates_shown) == 2
    assert alpha.hidden_candidates == 1


def test_metric_union_and_deterministic_column_order():
    report = _single_report_with_matching()
    ctx = _single_context()["targets"]["__single__"]
    blocks = build_matching_debug_blocks_for_target(
        _single_target_wrapper(report), ctx, top_k=10
    )
    alpha = next(b for b in blocks if b.source.id == "s.alpha")

    assert collect_metric_columns(alpha.candidates_shown) == [
        "ast",
        "mod",
        "module_distance",
        "custom_metric",
    ]


def test_html_metric_heatmap_normalization_modes():
    report = _single_report_with_matching()
    ctx = _single_context()["targets"]["__single__"]
    blocks = build_matching_debug_blocks_for_target(
        _single_target_wrapper(report), ctx, top_k=10
    )
    alpha = next(b for b in blocks if b.source.id == "s.alpha")
    norms = compute_metric_normalization(alpha.candidates_shown, alpha.metric_columns)

    assert norms["ast"]["mode"] == "direct"
    assert norms["custom_metric"]["mode"] in {"constant", "minmax"}


def test_module_distance_is_inverted_for_debug_display():
    report = _single_report_with_matching()
    ctx = _single_context()["targets"]["__single__"]
    blocks = build_matching_debug_blocks_for_target(
        _single_target_wrapper(report), ctx, top_k=10
    )
    alpha = next(b for b in blocks if b.source.id == "s.alpha")

    module_distances = [
        candidate.confidence_metrics["module_distance"]
        for candidate in alpha.candidates_shown
    ]

    assert module_distances[0] == 1.0
    assert module_distances[1] == 0.5
    assert module_distances[2] == pytest.approx(1.0 / 3.0, rel=1e-6)


def _target(target_id: str, name: str, matched: str) -> TargetReport:
    """A passing target whose one match pairs the reference's ``s1`` with
    ``matched``."""
    matches = (
        {
            "source_entity_id": "s1",
            "status": "matched",
            "target_entity_id": matched,
            "confidence": 1.0,
            "candidates": [],
        },
    )
    return TargetReport(
        target_id=target_id,
        display_name=name,
        source_root="/src",
        target_path=f"/targets/{target_id}",
        tags=(),
        mode="static-only",
        matching=MatchingSection(
            matches=matches, matching_config={}, summary=matching_summary(matches)
        ),
        results=(),
        summary=results_summary({}),
        artifacts=(),
        exit_code=0,
    )


def _two_target_document() -> ReportDocument:
    """A run report of two passing targets, ``A Project`` and ``B Project``."""
    run = RunMeta(
        generated_at="2026-02-22T00:00:00Z",
        target_path=None,
        source_path="/src",
        reference_modules=(),
        config_snapshot=None,
        config_fingerprint=None,
        tool_version="test",
        mode="static-only",
    )
    return ReportDocument(
        schema_version="2",
        framework_version="test",
        generated_at=run.generated_at,
        run=run,
        targets=(_target("a", "A Project", "ta"), _target("b", "B Project", "tb")),
        summary=AggregateSummary(
            targets_total=2,
            targets_failed=0,
            targets_passed=2,
            results=results_summary({}),
        ),
        exit_code=0,
        kind="run",
    )


def test_markdown_bundle_matching_debug_isolated_per_target(tmp_path: Path):
    report = _two_target_document()
    ctx = {
        "kind": "run",
        "targets": {
            ("A Project", "/targets/a"): {
                "sources": {
                    "s1": {
                        "id": "s1",
                        "name": "Source A",
                        "type": "function",
                        "location": "a.py:1",
                    }
                },
                "targets": {
                    "ta": {
                        "id": "ta",
                        "name": "Target A",
                        "type": "function",
                        "location": "ta.py:1",
                    }
                },
            },
            ("B Project", "/targets/b"): {
                "sources": {
                    "s1": {
                        "id": "s1",
                        "name": "Source B",
                        "type": "function",
                        "location": "b.py:1",
                    }
                },
                "targets": {
                    "tb": {
                        "id": "tb",
                        "name": "Target B",
                        "type": "function",
                        "location": "tb.py:1",
                    }
                },
            },
        },
    }

    md_root = tmp_path / "md"
    render_markdown_bundle(
        report,
        md_root,
        matching_debug_context=ctx,
        detail="debug",
    )

    a_md = (md_root / "targets" / "a.md").read_text(encoding="utf-8")
    b_md = (md_root / "targets" / "b.md").read_text(encoding="utf-8")

    assert "Source A" in a_md and "Source B" not in a_md
    assert "Source B" in b_md and "Source A" not in b_md
