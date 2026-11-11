from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, cast

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult, RuleStatus
from pythonarchtesting.dynamic.translation import NameTranslation
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult

from .messages import build_rule_result

if TYPE_CHECKING:
    from pythonarchtesting.dynamic.runner import ProbeOutcome

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


@dataclass(frozen=True)
class _FlowParams:
    """The ``enforce_flow`` parameters every run of the rule reads.

    ``spans`` is not among them: it is read only when the reference runs,
    as it always was, so a rule that stops earlier never touches it.
    """

    variable: str
    stages: list[str]
    cases: list[dict[str, Any]]
    timeout_s: float
    init: Any

    @classmethod
    def from_rule(cls, rule: Rule) -> _FlowParams:
        return cls(
            variable=str(rule.params.get("variable")),
            stages=[str(stage) for stage in rule.params.get("stages") or []],
            cases=list(rule.params.get("cases") or []),
            timeout_s=float(rule.params.get("timeout_s", 5.0)),
            init=rule.params.get("init"),
        )


# A verdict reached before the target's stage order is judged: the status,
# and the reason and summary that ``details`` reports for it.
_Problem = tuple[RuleStatus, str, str]


def _precondition_problem(
    source: Entity, target: Entity, ctx: EvalContext
) -> _Problem | None:
    """Why the rule cannot run at all, or None when both runs may start.

    Without ``--dynamic`` nothing runs, so the rule is skipped; a target of
    another kind than the reference cannot be called with the same cases.
    """
    if ctx.target_root is None or ctx.source_root is None:
        return (
            "SKIPPED",
            "dynamic_checks_disabled",
            "dynamic checks are off; run with --dynamic",
        )
    if target.kind not in _SUPPORTED_KINDS or target.kind != source.kind:
        return (
            "FAILED",
            "target_kind_mismatch",
            f"expected a {source.kind}, matched a {target.kind}",
        )
    return None


def _run_reference(
    rule: Rule, source: Entity, ctx: EvalContext, params: _FlowParams
) -> ProbeOutcome:
    """Run the reference on the rule's cases, recording each stage's calls.

    The runner is imported when called, not with this module, so that a
    test replacing ``runner.run_cases`` is seen by the evaluator.
    """
    from pythonarchtesting.dynamic.runner import run_reference_cases

    spans = list(rule.params.get("spans") or [])
    return run_reference_cases(
        getattr(ctx, "reference_runs", None),
        target_root=ctx.source_root,
        module_path=source.module_path,
        qualname=source.qualname,
        kind=source.kind,
        cases=[{**case, "capture_stages": {"spans": spans}} for case in params.cases],
        init=params.init,
        timeout_s=params.timeout_s,
        sandbox=ctx.sandbox,
    )


def _reference_problem(
    reference: ProbeOutcome, details: dict[str, Any]
) -> _Problem | None:
    """Record the reference run; say why it cannot serve as the expectation.

    A probe that did not complete reports its own status and error; a
    completed probe fails on its first case that did not pass. Either is an
    error of the rule, not a failure of the target.
    """
    details["reference_status"] = reference.status
    problem = _first_failure(reference.cases)
    if reference.status != "completed":
        cause = f"{reference.status}: {reference.error or 'no detail'}"
    elif problem is not None:
        cause = f"case {problem[0]}: {problem[1]}"
    else:
        return None
    if reference.stderr:
        details["reference_stderr_tail"] = reference.stderr
    return ("ERROR", "reference_failed", f"the reference itself did not run: {cause}")


def _stage_listing(expected: list[list[Any]]) -> list[list[list[Any]]]:
    """Each case's stages with the qualified names of the calls they made."""
    return [
        [[stage, [call.get("qualname") for call in calls]] for stage, calls in run]
        for run in expected
    ]


def _reference_stage_problem(
    stages: list[str], expected: list[list[Any]], details: dict[str, Any]
) -> _Problem | None:
    """Record the stages the reference reached; say why they cannot be checked.

    Every case has to reach every declared stage, and at least one stage has
    to call a project function, or the target's stages cannot be told apart.
    ``unchecked_stages`` is recorded only once every case reached every
    stage, as the report has always shown it.
    """
    details["reference_stages"] = _stage_listing(expected)
    for index, reached in enumerate(expected):
        missing = _missing_stages(stages, reached)
        if missing:
            return (
                "ERROR",
                "reference_misses_stage",
                f"case {index} never reaches stage(s) {', '.join(missing)} "
                "in the reference; choose arguments that exercise every stage",
            )
    checked = {str(stage) for run in expected for stage, calls in run if calls}
    details["unchecked_stages"] = [stage for stage in stages if stage not in checked]
    if not checked:
        return (
            "ERROR",
            "reference_stages_call_nothing",
            "no stage of the reference calls a function of the project, so "
            "the target's stages cannot be told apart; label statements "
            "that call the project's own functions",
        )
    return None


def _run_target(
    source: Entity, target: Entity, ctx: EvalContext, params: _FlowParams
) -> ProbeOutcome:
    """Run the target on the same cases, recording the project calls it makes.

    The cases and ``init`` are translated to the target's names first. The
    runner is imported when called for the same reason as in
    ``_run_reference``.
    """
    from pythonarchtesting.dynamic.runner import run_cases

    names = NameTranslation.from_context(ctx)
    return run_cases(
        # Set: ``_precondition_problem`` stops the rule before this otherwise.
        target_root=cast(Path, ctx.target_root),
        module_path=target.module_path,
        qualname=target.qualname,
        kind=target.kind,
        cases=[
            {**case, "flow_calls": True}
            for case in names.cases(params.cases, source, target)
        ],
        init=names.value(params.init, source, target),
        timeout_s=params.timeout_s,
        sandbox=ctx.sandbox,
    )


def _target_problem(outcome: ProbeOutcome, details: dict[str, Any]) -> _Problem | None:
    """Record the target run; say why its calls cannot be judged, or None.

    A probe that did not complete and a case that could not be set up are
    both failures of the target, unlike the same problems in the reference.
    """
    details["probe_status"] = outcome.status
    details["cases"] = outcome.cases
    if outcome.stderr:
        details["stderr_tail"] = outcome.stderr
    if outcome.status != "completed":
        return (
            "FAILED",
            f"probe_{outcome.status}",
            f"{outcome.status}: {outcome.error or 'no detail'}",
        )
    broken = _first_failure(outcome.cases)
    if broken is not None:
        return (
            "FAILED",
            "case_setup_failed",
            f"case {broken[0]} could not run: {broken[1]}",
        )
    return None


def _first_order_failure(
    outcome: ProbeOutcome, expected: list[list[Any]], ctx: EvalContext
) -> tuple[list[str], str] | None:
    """The stages reached and the summary of the first case out of order.

    Target cases are paired with the reference's by position. The summary
    names the case and, when the target's call raised, what it raised.
    """
    translate = _translator(ctx)
    for case, run in zip(outcome.cases, expected):
        called = [str(call.get("qualname")) for call in case.get("flow_calls") or []]
        reached, failure = _stage_order(run, called, translate)
        if failure is not None:
            raised = case.get("raised")
            suffix = f"; the call raised {raised}" if raised else ""
            return reached, f"case {case.get('index')}: {failure}{suffix}"
    return None


def _passed_summary(case_count: int, unchecked: list[str]) -> str:
    """The summary of a target that called every stage's functions in order."""
    note = (
        f"; stage(s) {', '.join(map(repr, unchecked))} call no project "
        "function and were not checked"
        if unchecked
        else ""
    )
    return f"{case_count} case(s) ran the stages' operations in order{note}"


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
        params = _FlowParams.from_rule(rule)
        # "reason" and "summary" come first whatever step sets them.
        details: dict[str, Any] = {
            "reason": "",
            "summary": "",
            "variable": params.variable,
            "stages": params.stages,
        }

        def result(status: RuleStatus) -> RuleResult:
            return build_rule_result(rule, source, target, match, status, details, ())

        def stop(problem: _Problem) -> RuleResult:
            status, details["reason"], details["summary"] = problem
            return result(status)

        problem = _precondition_problem(source, target, ctx)
        if problem is not None:
            return stop(problem)

        reference = _run_reference(rule, source, ctx, params)
        problem = _reference_problem(reference, details)
        if problem is not None:
            return stop(problem)

        expected = [list(case.get("stages") or []) for case in reference.cases]
        problem = _reference_stage_problem(params.stages, expected, details)
        if problem is not None:
            return stop(problem)

        outcome = _run_target(source, target, ctx, params)
        problem = _target_problem(outcome, details)
        if problem is not None:
            return stop(problem)

        order = _first_order_failure(outcome, expected, ctx)
        if order is not None:
            details["stages_reached"], summary = order
            return stop(("FAILED", "stage_order_mismatch", summary))

        details["reason"] = "stages_reached_in_order"
        details["summary"] = _passed_summary(
            len(params.cases), details["unchecked_stages"]
        )
        return result("OK")


__all__ = ["RuntimeFlowEvaluator"]
