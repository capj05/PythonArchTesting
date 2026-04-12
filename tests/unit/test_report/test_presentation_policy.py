from __future__ import annotations

from pythonarchtesting.report.ir.models import (
    EntityRef,
    MatchingSection,
    MatchingSummary,
    ResultItem,
    ResultsSummary,
    TargetReport,
)
from pythonarchtesting.report.presentation.models import (
    CompactPassedSummary,
    MatchingPresentation,
    TargetPresentation,
)
from pythonarchtesting.report.presentation.policy import (
    derive_matching_visibility,
    derive_run_display_status,
    derive_target_display_status,
)


def _result(
    *,
    result_id: str,
    rule_id: str = "rule/test",
    status: str = "OK",
    severity: str = "info",
    match_status: str | None = "matched",
) -> ResultItem:
    return ResultItem(
        result_id=result_id,
        project_id="proj",
        rule_id=rule_id,
        rule_type="arch/test",
        category="arch",
        status=status,
        severity=severity,
        message=f"{status} message",
        source_entity_id="src",
        target_entity_id="tgt",
        match_status=match_status,
        confidence=1.0,
        source=EntityRef(
            module="pkg.src",
            qualname="Service.run",
            file="src.py",
            line=10,
            cls="Service",
            function="run",
        ),
        target=EntityRef(
            module="pkg.tgt",
            qualname="Service.run",
            file="tgt.py",
            line=20,
            cls="Service",
            function="run",
        ),
        evidence=tuple(),
        details={},
        fix_hints=tuple(),
        tags=tuple(),
        timing_seconds=None,
        activation_source=None,
        stable_key=("sev", "status", "rule", "src", "tgt"),
        ordering_key=(0, result_id),
        extras={},
    )


def _target(
    *results: ResultItem,
    exit_code: int = 0,
    matched: int = 0,
    low_confidence: int = 0,
    ambiguous: int = 0,
    unmatched: int = 0,
) -> TargetReport:
    return TargetReport(
        target_id="alpha",
        display_name="Alpha",
        source_root="/src",
        target_path="/targets/alpha",
        tags=tuple(),
        mode="static-only",
        matching=MatchingSection(
            matches=tuple(),
            matching_config={},
            summary=MatchingSummary(
                total=matched + low_confidence + ambiguous + unmatched,
                matched=matched,
                low_confidence=low_confidence,
                ambiguous=ambiguous,
                unmatched=unmatched,
            ),
        ),
        results=tuple(results),
        summary=ResultsSummary(
            results_total=len(results),
            status_counts={},
            severity_counts={},
            category_counts={},
            top_rules=tuple(),
            top_source_files=tuple(),
            timings=None,
        ),
        artifacts=tuple(),
        exit_code=exit_code,
    )


def _target_presentation(status: str) -> TargetPresentation:
    return TargetPresentation(
        title="Target Report: Alpha",
        target_id="alpha",
        display_name="Alpha",
        target_path="/targets/alpha",
        display_status=status,  # type: ignore[arg-type]
        exit_code=0,
        issue_groups=tuple(),
        warning_groups=tuple(),
        compact_passed_summary=CompactPassedSummary(
            passed_total=0, top_passed_rules=tuple(), hidden_passed_count=0
        ),
        matching_summary=MatchingPresentation(
            total=0,
            matched=0,
            low_confidence=0,
            ambiguous=0,
            unmatched=0,
            visibility="hidden",
            reason=None,
        ),
        debug_sections_allowed=False,
        mode="standard",
    )


def test_derive_target_display_statuses() -> None:
    assert derive_target_display_status(_target(_result(result_id="ok"))) == "OK"
    assert (
        derive_target_display_status(
            _target(_result(result_id="warn", status="WARNING", severity="warning"))
        )
        == "WARNINGS ONLY"
    )
    assert (
        derive_target_display_status(
            _target(_result(result_id="skip", status="SKIPPED", severity="warning"))
        )
        == "WARNINGS ONLY"
    )
    assert (
        derive_target_display_status(
            _target(_result(result_id="fail", status="FAILED", severity="error"))
        )
        == "ISSUES"
    )
    assert (
        derive_target_display_status(
            _target(_result(result_id="err", status="ERROR", severity="error"))
        )
        == "ERROR"
    )
    assert (
        derive_target_display_status(_target(_result(result_id="ok"), exit_code=1))
        == "ISSUES"
    )


def test_derive_run_display_statuses() -> None:
    class _Document:
        def __init__(self, exit_code: int) -> None:
            self.exit_code = exit_code

    assert (
        derive_run_display_status(_Document(0), (_target_presentation("OK"),)) == "OK"
    )
    assert (
        derive_run_display_status(
            _Document(0), (_target_presentation("WARNINGS ONLY"),)
        )
        == "WARNINGS ONLY"
    )
    assert (
        derive_run_display_status(_Document(0), (_target_presentation("ISSUES"),))
        == "ISSUES"
    )
    assert (
        derive_run_display_status(_Document(0), (_target_presentation("ERROR"),))
        == "ERROR"
    )
    assert (
        derive_run_display_status(_Document(1), (_target_presentation("OK"),))
        == "ISSUES"
    )


def test_derive_matching_visibility_by_mode() -> None:
    target = _target(_result(result_id="ok"), low_confidence=1)
    visibility, reason = derive_matching_visibility(
        target, mode="standard", visible_groups=tuple()
    )
    assert visibility == "hidden"
    assert reason is None

    visibility, reason = derive_matching_visibility(
        target,
        mode="verbose",
        visible_groups=(type("Group", (), {"show_matching_context": False})(),),
    )
    assert visibility == "summary_only"
    assert reason == "matching summary explains uncertainty"

    visibility, reason = derive_matching_visibility(
        _target(_result(result_id="skip", status="SKIPPED", severity="warning")),
        mode="verbose",
        visible_groups=(type("Group", (), {"show_matching_context": True})(),),
    )
    assert visibility == "contextual"
    assert reason == "visible result groups require matching context"

    visibility, reason = derive_matching_visibility(
        _target(_result(result_id="ok"), matched=1),
        mode="debug",
        visible_groups=tuple(),
    )
    assert visibility == "debug_only"
    assert reason == "matching data available for debug appendices"
