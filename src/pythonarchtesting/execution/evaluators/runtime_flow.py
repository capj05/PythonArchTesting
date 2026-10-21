from __future__ import annotations

from typing import Any, Callable

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult

from .messages import _build_rule_result

_SUPPORTED_KINDS = frozenset({"function", "method"})
_REPORTED_CALLS = 50


def _first_failure(cases: list[dict[str, Any]]) -> tuple[int, str] | None:
    for case in cases:
        if case.get("status") != "passed":
            failures = case.get("failures") or ["no detail"]
            return int(case.get("index", 0)), str(failures[0])
    return None


def _missing_stages(declared: list[str], reached: list[list[Any]]) -> list[str]:
    seen = {str(stage) for stage, _ in reached}
    return [stage for stage in declared if stage not in seen]


def _translator(ctx: EvalContext) -> Callable[[dict[str, Any]], str]:
    """Map a function the reference called to its name in the target.

    The reference's functions are matched to the target's by the normal
    matching step, so a helper the target renamed or moved is still the same
    operation; an unmatched one keeps its reference name.
    """
    by_name = {
        (entity.module_path, entity.qualname): entity
        for entity in ctx.source_by_id.values()
    }

    def translate(call: dict[str, Any]) -> str:
        qualname = str(call.get("qualname"))
        entity = by_name.get((str(call.get("module")), qualname))
        match = ctx.matches.get(entity.canonical_id) if entity is not None else None
        target_id = getattr(match, "target_id", None)
        target = ctx.target_by_id.get(target_id) if target_id else None
        return str(target.qualname) if target is not None else qualname

    return translate


def _stage_order(
    stages: list[list[Any]],
    called: list[str],
    translate: Callable[[dict[str, Any]], str],
) -> tuple[list[str], str | None]:
    """Stages whose calls the target makes in order, and the first that fails.

    Each stage is identified by the project functions the reference calls
    while running it; the target has to call them in the same order, with
    any other calls in between. A stage that calls no project function says
    nothing about the target and is skipped.
    """
    position = 0
    reached: list[str] = []
    for stage, stage_calls in stages:
        expected = [translate(call) for call in stage_calls]
        if not expected:
            continue
        for name in expected:
            while position < len(called) and called[position] != name:
                position += 1
            if position == len(called):
                shown = called[:_REPORTED_CALLS]
                more = " ..." if len(called) > _REPORTED_CALLS else ""
                when = (
                    "never calls it" if name not in called else "calls it only earlier"
                )
                return reached, (
                    f"stage {stage!r} calls {name}() after "
                    f"{reached or 'the start'}, but the target {when}; "
                    f"target calls: {shown}{more}"
                )
            position += 1
        reached.append(str(stage))
    return reached, None


class RuntimeFlowEvaluator:
    """Evaluator for ``enforce_flow(..., cases=[...])`` rules.

    The reference function runs first, with its flow-annotated statements
    known from the compiler, and reports the project functions each stage
    calls. The target then runs the same cases and has to call those
    functions in the same stage order. Values are never compared: two targets
    that compute different results through the same stages get the same
    verdict. Both runs happen only when ``ctx.target_root`` and
    ``ctx.source_root`` are set, that is with ``--dynamic``.
    """

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        variable = str(rule.params.get("variable"))
        stages = [str(stage) for stage in rule.params.get("stages") or []]
        cases: list[dict[str, Any]] = list(rule.params.get("cases") or [])
        timeout_s = float(rule.params.get("timeout_s", 5.0))
        init = rule.params.get("init")
        details: dict[str, Any] = {
            "reason": "",
            "summary": "",
            "variable": variable,
            "stages": stages,
        }

        def result(status: Any) -> RuleResult:
            return _build_rule_result(rule, source, target, match, status, details, ())

        if ctx.target_root is None or ctx.source_root is None:
            details["reason"] = "dynamic_checks_disabled"
            details["summary"] = "dynamic checks are off; run with --dynamic"
            return result("SKIPPED")

        if target.kind not in _SUPPORTED_KINDS or target.kind != source.kind:
            details["reason"] = "target_kind_mismatch"
            details["summary"] = f"expected a {source.kind}, matched a {target.kind}"
            return result("FAILED")

        from pythonarchtesting.dynamic.runner import run_cases

        spans = list(rule.params.get("spans") or [])
        reference = run_cases(
            target_root=ctx.source_root,
            module_path=source.module_path,
            qualname=source.qualname,
            kind=source.kind,
            cases=[{**case, "capture_stages": {"spans": spans}} for case in cases],
            init=init,
            timeout_s=timeout_s,
            sandbox=ctx.sandbox,
        )
        details["reference_status"] = reference.status
        problem = _first_failure(reference.cases)
        if reference.status != "completed" or problem is not None:
            details["reason"] = "reference_failed"
            if reference.status != "completed":
                cause = f"{reference.status}: {reference.error or 'no detail'}"
            else:
                index, message = problem or (0, "no detail")
                cause = f"case {index}: {message}"
            details["summary"] = f"the reference itself did not run: {cause}"
            if reference.stderr:
                details["reference_stderr_tail"] = reference.stderr
            return result("ERROR")

        expected = [list(case.get("stages") or []) for case in reference.cases]
        details["reference_stages"] = [
            [[stage, [call.get("qualname") for call in calls]] for stage, calls in run]
            for run in expected
        ]
        for index, reached in enumerate(expected):
            missing = _missing_stages(stages, reached)
            if missing:
                details["reason"] = "reference_misses_stage"
                details["summary"] = (
                    f"case {index} never reaches stage(s) {', '.join(missing)} "
                    "in the reference; choose arguments that exercise every stage"
                )
                return result("ERROR")
        checked = {str(stage) for run in expected for stage, calls in run if calls}
        details["unchecked_stages"] = [
            stage for stage in stages if stage not in checked
        ]
        if not checked:
            details["reason"] = "reference_stages_call_nothing"
            details["summary"] = (
                "no stage of the reference calls a function of the project, so "
                "the target's stages cannot be told apart; label statements "
                "that call the project's own functions"
            )
            return result("ERROR")

        outcome = run_cases(
            target_root=ctx.target_root,
            module_path=target.module_path,
            qualname=target.qualname,
            kind=target.kind,
            cases=[{**case, "flow_calls": True} for case in cases],
            init=init,
            timeout_s=timeout_s,
            sandbox=ctx.sandbox,
        )
        details["probe_status"] = outcome.status
        details["cases"] = outcome.cases
        if outcome.stderr:
            details["stderr_tail"] = outcome.stderr
        if outcome.status != "completed":
            details["reason"] = f"probe_{outcome.status}"
            details["summary"] = f"{outcome.status}: {outcome.error or 'no detail'}"
            return result("FAILED")
        broken = _first_failure(outcome.cases)
        if broken is not None:
            details["reason"] = "case_setup_failed"
            details["summary"] = f"case {broken[0]} could not run: {broken[1]}"
            return result("FAILED")

        translate = _translator(ctx)
        for case, run in zip(outcome.cases, expected):
            called = [
                str(call.get("qualname")) for call in case.get("flow_calls") or []
            ]
            reached, failure = _stage_order(run, called, translate)
            if failure is not None:
                raised = case.get("raised")
                suffix = f"; the call raised {raised}" if raised else ""
                details["stages_reached"] = reached
                details["reason"] = "stage_order_mismatch"
                details["summary"] = f"case {case.get('index')}: {failure}{suffix}"
                return result("FAILED")

        details["reason"] = "stages_reached_in_order"
        unchecked = details["unchecked_stages"]
        note = (
            f"; stage(s) {', '.join(map(repr, unchecked))} call no project "
            "function and were not checked"
            if unchecked
            else ""
        )
        details["summary"] = (
            f"{len(cases)} case(s) ran the stages' operations in order{note}"
        )
        return result("OK")


__all__ = ["RuntimeFlowEvaluator"]
