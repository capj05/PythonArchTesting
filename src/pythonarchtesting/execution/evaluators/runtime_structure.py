from __future__ import annotations

from typing import Any

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult

from .messages import _build_rule_result

_SUPPORTED_TARGET_KINDS = frozenset({"function", "method"})


def _in_module(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def _describe_call(call: dict[str, Any]) -> str:
    return (
        f"{call.get('caller')} calls {call.get('module')}:{call.get('callee')} "
        f"(line {call.get('line')})"
    )


def _describe_write(write: dict[str, Any]) -> str:
    return (
        f"{write.get('writer')} sets {write.get('class')}.{write.get('attribute')} "
        f"at {write.get('file')}:{write.get('line')}"
    )


def _line_ranges(lines: list[int]) -> str:
    """``[3, 4, 5, 9]`` as ``"3-5, 9"``."""
    spans: list[list[int]] = []
    for line in sorted(lines):
        if spans and line == spans[-1][1] + 1:
            spans[-1][1] = line
        else:
            spans.append([line, line])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in spans)


def _coverage(cases: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Lines of the target's own code that ran in at least one case.

    A dynamic check only sees what runs: a line no case executed was not
    checked, so a passing verdict holds for the executed lines only.
    """
    reports = [case["lines"] for case in cases if case.get("lines")]
    if not reports:
        return None
    missed = set(reports[0]["missed"]).intersection(
        *(report["missed"] for report in reports[1:])
    )
    total = len(set(reports[0]["missed"]) | set(reports[0]["run"]))
    return {
        "file": reports[0]["file"],
        "lines_total": total,
        "lines_run": total - len(missed),
        "unexercised_lines": sorted(missed),
    }


def _coverage_note(coverage: dict[str, Any] | None) -> str:
    if not coverage or not coverage["unexercised_lines"]:
        return ""
    return (
        f"; no case ran lines {_line_ranges(coverage['unexercised_lines'])} "
        f"of {coverage['file']}, so they were not checked"
    )


def _missed_in_case(case: dict[str, Any]) -> str:
    """Why a call may be absent: the code that would make it did not run."""
    missed = (case.get("lines") or {}).get("missed") or []
    if not missed:
        return ""
    return f"; lines {_line_ranges(missed)} did not run in this case"


def _reference_cannot_run(
    rule: Rule, source: Entity, ctx: EvalContext, index: int
) -> bool:
    """Whether case ``index`` cannot even be set up on the reference.

    Run only after the target failed to set the case up, so passing targets
    cost nothing extra. Without a source root (or if the reference run
    itself times out or crashes) the case is not blamed on the reference.
    """
    source_root = getattr(ctx, "source_root", None)
    if source_root is None:
        return False
    cases = list(rule.params.get("cases") or [])
    if not 0 <= index < len(cases):
        return False
    from pythonarchtesting.dynamic.batch import observation
    from pythonarchtesting.dynamic.runner import run_cases

    outcome = run_cases(
        target_root=source_root,
        module_path=source.module_path,
        qualname=source.qualname,
        kind=source.kind,
        cases=[cases[index]],
        init=rule.params.get("init"),
        timeout_s=float(rule.params.get("timeout_s", 5.0)),
        sandbox=ctx.sandbox,
        observe=observation(rule),
    )
    return outcome.status == "completed" and any(
        case.get("status") == "error" for case in outcome.cases
    )


class _ObservingEvaluator:
    """Shared driver: run the cases with the probe and judge what it observed.

    Cases only drive execution. A case whose call raises still counts, with
    whatever it did before raising; a case that cannot even be set up fails
    the rule, because nothing was observed.
    """

    supported_kinds = _SUPPORTED_TARGET_KINDS

    def _violations(
        self, rule: Rule, cases: list[dict[str, Any]], details: dict[str, Any]
    ) -> list[str]:
        raise NotImplementedError

    def _passed_summary(self, rule: Rule, case_count: int) -> str:
        raise NotImplementedError

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        cases: list[dict[str, Any]] = list(rule.params.get("cases") or [])
        details: dict[str, Any] = {
            "reason": "",
            "summary": "",
            "case_count": len(cases),
            "cases": [],
        }

        if ctx.target_root is None:
            details["reason"] = "dynamic_checks_disabled"
            details["summary"] = "dynamic checks are off; run with --dynamic"
            return _build_rule_result(
                rule, source, target, match, "SKIPPED", details, ()
            )

        if target.kind not in self.supported_kinds or target.kind != source.kind:
            details["reason"] = "target_kind_mismatch"
            details["summary"] = f"expected a {source.kind}, matched a {target.kind}"
            return _build_rule_result(
                rule, source, target, match, "FAILED", details, ()
            )

        from pythonarchtesting.dynamic.batch import cache_key, observation
        from pythonarchtesting.dynamic.runner import run_cases

        batched = ctx.dynamic_cache.get(cache_key(rule, target))
        details["batched"] = batched is not None
        outcome = batched or run_cases(
            target_root=ctx.target_root,
            module_path=target.module_path,
            qualname=target.qualname,
            kind=target.kind,
            cases=cases,
            init=rule.params.get("init"),
            timeout_s=float(rule.params.get("timeout_s", 5.0)),
            sandbox=ctx.sandbox,
            observe=observation(rule),
        )
        details["probe_status"] = outcome.status
        details["cases"] = outcome.cases
        if outcome.error:
            details["error"] = outcome.error
        if outcome.stderr:
            details["stderr_tail"] = outcome.stderr

        if outcome.status != "completed":
            details["reason"] = f"probe_{outcome.status}"
            details["summary"] = f"{outcome.status}: {outcome.error or 'no detail'}"
            return _build_rule_result(
                rule, source, target, match, "FAILED", details, ()
            )
        broken = [case for case in outcome.cases if case.get("status") == "error"]
        if broken:
            first = broken[0]
            failure = (first.get("failures") or ["no detail"])[0]
            if _reference_cannot_run(rule, source, ctx, int(first.get("index", 0))):
                # The case is wrong for the reference too: the reference's
                # author has to fix it, not the student.
                details["reason"] = "reference_case_invalid"
                details["summary"] = (
                    f"case {first.get('index')} cannot run on the reference "
                    f"either: {failure}"
                )
                return _build_rule_result(
                    rule, source, target, match, "ERROR", details, ()
                )
            details["reason"] = "case_setup_failed"
            details["summary"] = f"case {first.get('index')} could not run: {failure}"
            return _build_rule_result(
                rule, source, target, match, "FAILED", details, ()
            )

        details["target_module"] = target.module_path
        coverage = _coverage(outcome.cases)
        if coverage is not None:
            details["coverage"] = coverage
        violations = self._violations(rule, outcome.cases, details)
        if not violations:
            details["reason"] = "no_violations"
            details["summary"] = self._passed_summary(
                rule, len(cases)
            ) + _coverage_note(coverage)
            return _build_rule_result(rule, source, target, match, "OK", details, ())
        details["violations"] = violations
        details["reason"] = "violation"
        more = f" (+{len(violations) - 1} more)" if len(violations) > 1 else ""
        details["summary"] = violations[0] + more
        return _build_rule_result(rule, source, target, match, "FAILED", details, ())


class RuntimeCallsEvaluator(_ObservingEvaluator):
    """Evaluator for ``forbid_runtime_calls`` and ``require_runtime_calls``."""

    def _violations(
        self, rule: Rule, cases: list[dict[str, Any]], details: dict[str, Any]
    ) -> list[str]:
        modules = [str(name) for name in rule.params.get("modules") or []]
        allow = [str(name) for name in rule.params.get("allow") or []]
        details["modules"] = modules
        violations: list[str] = []
        for case in cases:
            calls = list(case.get("calls") or [])
            if rule.params.get("mode") == "require":
                for module in modules:
                    if not any(_in_module(str(c["module"]), module) for c in calls):
                        raised = case.get("raised")
                        suffix = f"; the call raised {raised}" if raised else ""
                        violations.append(
                            f"case {case.get('index')}: no direct call into "
                            f"{module}{suffix}{_missed_in_case(case)}"
                        )
                continue
            for call in calls:
                name = str(call["module"])
                if any(_in_module(name, prefix) for prefix in allow):
                    continue
                if any(_in_module(name, prefix) for prefix in modules):
                    violations.append(
                        f"case {case.get('index')}: {_describe_call(call)}"
                    )
        return violations

    def _passed_summary(self, rule: Rule, case_count: int) -> str:
        modules = ", ".join(rule.params.get("modules") or [])
        if rule.params.get("mode") == "require":
            return f"every case called into {modules} ({case_count} case(s))"
        return f"no call into {modules} in {case_count} case(s)"


class RuntimeWritesEvaluator(_ObservingEvaluator):
    """Evaluator for ``forbid_foreign_writes``."""

    def _violations(
        self, rule: Rule, cases: list[dict[str, Any]], details: dict[str, Any]
    ) -> list[str]:
        _ = rule, details
        return [
            f"case {case.get('index')}: {_describe_write(write)}"
            for case in cases
            for write in case.get("writes") or []
        ]

    def _passed_summary(self, rule: Rule, case_count: int) -> str:
        _ = rule
        return f"no foreign attribute writes in {case_count} case(s)"


def _describe_instance(instance: dict[str, Any]) -> str:
    return (
        f"{instance.get('creator')} creates {instance.get('module')}:"
        f"{instance.get('class')} at {instance.get('file')}:{instance.get('line')}"
    )


class RuntimeInstancesEvaluator(_ObservingEvaluator):
    """Evaluator for ``forbid_runtime_instantiation``.

    The probe reports every project class instantiated by project code; only
    objects created by code of the target's own module count here.
    """

    def _violations(
        self, rule: Rule, cases: list[dict[str, Any]], details: dict[str, Any]
    ) -> list[str]:
        modules = [str(name) for name in rule.params.get("modules") or []]
        allow = [str(name) for name in rule.params.get("allow") or []]
        own = str(details.get("target_module"))
        violations: list[str] = []
        for case in cases:
            for instance in case.get("instances") or []:
                name = str(instance.get("module"))
                if instance.get("from") != own:
                    continue
                if any(_in_module(name, prefix) for prefix in allow):
                    continue
                if any(_in_module(name, prefix) for prefix in modules):
                    violations.append(
                        f"case {case.get('index')}: {_describe_instance(instance)}"
                    )
        return violations

    def _passed_summary(self, rule: Rule, case_count: int) -> str:
        modules = ", ".join(rule.params.get("modules") or [])
        return f"no instance of {modules} created in {case_count} case(s)"


def _edges(case: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """First call per ``(from, to)`` module pair, in the order they happened."""
    edges: dict[tuple[str, str], dict[str, Any]] = {}
    for call in case.get("calls") or []:
        edges.setdefault((str(call.get("from")), str(call.get("module"))), call)
    return edges


class RuntimeReferenceCallsEvaluator:
    """Evaluator for ``enforce_reference_calls``.

    The reference entity runs first on every case and its module-to-module
    calls inside the project form the allowed dependency graph; the target
    then runs the same cases. Both runs happen only with ``--dynamic``.
    """

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        cases: list[dict[str, Any]] = list(rule.params.get("cases") or [])
        timeout_s = float(rule.params.get("timeout_s", 5.0))
        require_all = bool(rule.params.get("require_all"))
        details: dict[str, Any] = {
            "reason": "",
            "summary": "",
            "case_count": len(cases),
            "require_all": require_all,
        }

        def result(status: Any) -> RuleResult:
            return _build_rule_result(rule, source, target, match, status, details, ())

        if ctx.target_root is None or ctx.source_root is None:
            details["reason"] = "dynamic_checks_disabled"
            details["summary"] = "dynamic checks are off; run with --dynamic"
            return result("SKIPPED")

        if target.kind not in _SUPPORTED_TARGET_KINDS or target.kind != source.kind:
            details["reason"] = "target_kind_mismatch"
            details["summary"] = f"expected a {source.kind}, matched a {target.kind}"
            return result("FAILED")

        from pythonarchtesting.dynamic.runner import run_cases

        reference = run_cases(
            target_root=ctx.source_root,
            module_path=source.module_path,
            qualname=source.qualname,
            kind=source.kind,
            cases=cases,
            init=rule.params.get("init"),
            timeout_s=timeout_s,
            sandbox=ctx.sandbox,
            observe={"calls": "edges"},
        )
        details["reference_status"] = reference.status
        broken = [case for case in reference.cases if case.get("status") == "error"]
        if reference.status != "completed" or broken:
            details["reason"] = "reference_failed"
            if reference.status != "completed":
                cause = f"{reference.status}: {reference.error or 'no detail'}"
            else:
                first = broken[0]
                cause = (
                    f"case {first.get('index')}: "
                    f"{(first.get('failures') or ['no detail'])[0]}"
                )
            details["summary"] = f"the reference itself did not run: {cause}"
            if reference.stderr:
                details["reference_stderr_tail"] = reference.stderr
            return result("ERROR")
        expected = [_edges(case) for case in reference.cases]
        details["reference_edges"] = [
            sorted(f"{a} -> {b}" for a, b in edges) for edges in expected
        ]

        outcome = run_cases(
            target_root=ctx.target_root,
            module_path=target.module_path,
            qualname=target.qualname,
            kind=target.kind,
            cases=cases,
            init=rule.params.get("init"),
            timeout_s=timeout_s,
            sandbox=ctx.sandbox,
            observe={"calls": "edges"},
        )
        details["probe_status"] = outcome.status
        details["cases"] = outcome.cases
        if outcome.stderr:
            details["stderr_tail"] = outcome.stderr
        if outcome.status != "completed":
            details["reason"] = f"probe_{outcome.status}"
            details["summary"] = f"{outcome.status}: {outcome.error or 'no detail'}"
            return result("FAILED")
        broken = [case for case in outcome.cases if case.get("status") == "error"]
        if broken:
            first = broken[0]
            details["reason"] = "case_setup_failed"
            details["summary"] = (
                f"case {first.get('index')} could not run: "
                f"{(first.get('failures') or ['no detail'])[0]}"
            )
            return result("FAILED")

        # Reflexion-model terms: a divergence is a call the reference does not
        # make, an absence a call of the reference the target does not make.
        divergences: list[str] = []
        absences: list[str] = []
        for case, allowed in zip(outcome.cases, expected):
            index = case.get("index")
            actual = _edges(case)
            for (origin, module), call in actual.items():
                if (origin, module) not in allowed:
                    divergences.append(
                        f"case {index}: {origin} -> {module} is not in the "
                        f"reference ({_describe_call(call)})"
                    )
            for origin, module in allowed:
                if (origin, module) not in actual:
                    raised = case.get("raised")
                    suffix = f"; the call raised {raised}" if raised else ""
                    absences.append(
                        f"case {index}: the reference's {origin} -> {module} "
                        f"never happened{suffix}{_missed_in_case(case)}"
                    )
        details["divergences"] = divergences
        details["absences"] = absences
        coverage = _coverage(outcome.cases)
        if coverage is not None:
            details["coverage"] = coverage
        violations = divergences + (absences if require_all else [])
        if not violations:
            details["reason"] = "no_violations"
            unmade = (
                f"; {len(absences)} reference call(s) never happened "
                "(not required without require_all)"
                if absences
                else ""
            )
            details["summary"] = (
                f"{len(cases)} case(s) used only the reference's module calls"
                + unmade
                + _coverage_note(coverage)
            )
            return result("OK")
        details["violations"] = violations
        details["reason"] = "violation"
        more = f" (+{len(violations) - 1} more)" if len(violations) > 1 else ""
        details["summary"] = violations[0] + more
        return result("FAILED")


class RuntimeMembersEvaluator(_ObservingEvaluator):
    """Evaluator for ``require_runtime_members`` and ``forbid_runtime_members``."""

    supported_kinds = frozenset({"class"})

    def _violations(
        self, rule: Rule, cases: list[dict[str, Any]], details: dict[str, Any]
    ) -> list[str]:
        _ = details
        names = [str(name) for name in rule.params.get("names") or []]
        require = rule.params.get("mode") == "require"
        violations: list[str] = []
        for case in cases:
            index = case.get("index")
            if not case.get("constructed"):
                violations.append(
                    f"case {index}: the instance could not be built: "
                    f"{case.get('raised') or 'no detail'}"
                )
                continue
            members = case.get("members") or {}
            for name in names:
                member = members.get(name) or {}
                if require and not member.get("present"):
                    violations.append(f"case {index}: the instance has no {name!r}")
                elif not require and member.get("present"):
                    violations.append(
                        f"case {index}: the instance has {name!r} "
                        f"(from {member.get('where')})"
                    )
        return violations

    def _passed_summary(self, rule: Rule, case_count: int) -> str:
        names = ", ".join(rule.params.get("names") or [])
        if rule.params.get("mode") == "require":
            return f"every instance has {names} ({case_count} case(s))"
        return f"no instance has {names} ({case_count} case(s))"


class RuntimeClassKindEvaluator(_ObservingEvaluator):
    """Evaluator for ``is_runtime_concrete_class`` and ``is_runtime_abstract_class``."""

    supported_kinds = frozenset({"class"})

    def _violations(
        self, rule: Rule, cases: list[dict[str, Any]], details: dict[str, Any]
    ) -> list[str]:
        _ = details
        violations: list[str] = []
        for case in cases:
            index = case.get("index")
            missing = ", ".join(case.get("abstract_methods") or [])
            if rule.params.get("expect") == "abstract":
                if not case.get("abstract"):
                    violations.append(
                        "the class is concrete at run time: no abstract method "
                        "is left unimplemented"
                    )
                continue
            if case.get("abstract"):
                violations.append(
                    f"case {index}: the class is abstract at run time; "
                    f"unimplemented: {missing}"
                )
            elif not case.get("constructed"):
                violations.append(
                    f"case {index}: constructing it raised "
                    f"{case.get('raised') or 'no detail'}"
                )
        return violations

    def _passed_summary(self, rule: Rule, case_count: int) -> str:
        if rule.params.get("expect") == "abstract":
            return "the class is abstract at run time"
        return f"instantiable in {case_count} case(s)"


class RuntimeProtocolEvaluator(_ObservingEvaluator):
    """Evaluator for ``implements_runtime_protocol``."""

    supported_kinds = frozenset({"class"})

    def _violations(
        self, rule: Rule, cases: list[dict[str, Any]], details: dict[str, Any]
    ) -> list[str]:
        _ = details
        methods: dict[str, int] = dict(rule.params.get("methods") or {})
        attributes = [str(name) for name in rule.params.get("attributes") or []]
        violations: list[str] = []
        for case in cases:
            index = case.get("index")
            if not case.get("constructed"):
                violations.append(
                    f"case {index}: the instance could not be built: "
                    f"{case.get('raised') or 'no detail'}"
                )
                continue
            members = case.get("members") or {}
            for name in attributes:
                if not (members.get(name) or {}).get("present"):
                    violations.append(f"case {index}: no attribute {name!r}")
            for name, arity in methods.items():
                member = members.get(name) or {}
                if not member.get("present"):
                    violations.append(f"case {index}: no method {name!r}")
                elif not member.get("callable"):
                    violations.append(f"case {index}: {name!r} is not callable")
                elif not member.get("bindable"):
                    violations.append(
                        f"case {index}: {name!r} does not accept {arity} "
                        "positional argument(s)"
                    )
        return violations

    def _passed_summary(self, rule: Rule, case_count: int) -> str:
        return (
            f"instances provide every member of {rule.params.get('protocol')} "
            f"({case_count} case(s))"
        )


def _singleton_violations(case: dict[str, Any]) -> list[str]:
    index = case.get("index")
    info = case.get("singleton") or {}
    access = info.get("access", "constructor")
    if info.get("error"):
        return [
            f"case {index}: obtaining the instance via {access} raised {info['error']}"
        ]
    if not info.get("same"):
        return [f"case {index}: two accesses via {access} returned different objects"]
    return []


def _observer_violations(rule: Rule, case: dict[str, Any]) -> list[str]:
    index = case.get("index")
    if not case.get("constructed"):
        return [
            f"case {index}: the subject could not be built: "
            f"{case.get('raised') or 'no detail'}"
        ]
    info = case.get("observer") or {}
    subscribe, notify = rule.params.get("subscribe"), rule.params.get("notify")
    if info.get("error"):
        return [f"case {index}: subscribing or notifying raised {info['error']}"]
    violations = []
    if not info.get("notified"):
        violations.append(
            f"case {index}: a listener registered with {subscribe}() was not "
            f"called by {notify}()"
        )
    if info.get("after_unsubscribe"):
        violations.append(
            f"case {index}: the listener was still called after "
            f"{rule.params.get('unsubscribe')}()"
        )
    return violations


def _delegation_violations(rule: Rule, case: dict[str, Any]) -> list[str]:
    spy = str(rule.params.get("spy"))
    member = rule.params.get("member")
    calls = [
        call
        for call in case.get("spy_calls") or []
        if call.get("spy") == spy and (member is None or call.get("member") == member)
    ]
    if calls:
        return []
    target = f"{spy}.{member}()" if member else spy
    raised = case.get("raised")
    suffix = f"; the call raised {raised}" if raised else ""
    return [
        f"case {case.get('index')}: never delegated to "
        f"{target}{suffix}{_missed_in_case(case)}"
    ]


class RuntimePatternEvaluator(_ObservingEvaluator):
    """Evaluator for ``is_runtime_singleton``, ``enforce_runtime_observer``,
    and ``require_runtime_delegation``."""

    supported_kinds = frozenset({"class", "function", "method"})

    def _violations(
        self, rule: Rule, cases: list[dict[str, Any]], details: dict[str, Any]
    ) -> list[str]:
        _ = details
        pattern = rule.params.get("pattern")
        violations: list[str] = []
        for case in cases:
            if pattern == "singleton":
                violations.extend(_singleton_violations(case))
            elif pattern == "observer":
                violations.extend(_observer_violations(rule, case))
            else:
                violations.extend(_delegation_violations(rule, case))
        return violations

    def _passed_summary(self, rule: Rule, case_count: int) -> str:
        pattern = rule.params.get("pattern")
        if pattern == "singleton":
            return f"one shared instance in {case_count} case(s)"
        if pattern == "observer":
            return f"listeners notified as declared in {case_count} case(s)"
        return f"delegated to {rule.params.get('spy')} in {case_count} case(s)"


__all__ = [
    "RuntimeCallsEvaluator",
    "RuntimeClassKindEvaluator",
    "RuntimeMembersEvaluator",
    "RuntimePatternEvaluator",
    "RuntimeProtocolEvaluator",
    "RuntimeInstancesEvaluator",
    "RuntimeReferenceCallsEvaluator",
    "RuntimeWritesEvaluator",
]
