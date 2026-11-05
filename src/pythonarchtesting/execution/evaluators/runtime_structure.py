from __future__ import annotations

from typing import Any

from pythonarchtesting.architecture.compare import fold_new_modules
from pythonarchtesting.core.models import EvalContext, Rule, RuleResult, RuleStatus
from pythonarchtesting.dynamic.translation import NameTranslation
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult

from .messages import _build_rule_result

_SUPPORTED_TARGET_KINDS = frozenset({"function", "method"})


def _in_module(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def _describe_call(call: dict[str, Any]) -> str:
    origin = call.get("origin")
    if origin:
        # A call another module made while the target ran: name the detour.
        chain = " -> ".join(
            [f"{origin.get('from')}:{origin.get('caller')}"]
            + [f"{step.get('module')}:{step.get('caller')}" for step in call["via"]]
        )
        return (
            f"{chain} calls {call.get('module')}:{call.get('callee')} "
            f"(line {call.get('line')} of {call.get('from')})"
        )
    return (
        f"{call.get('caller')} calls {call.get('module')}:{call.get('callee')} "
        f"(line {call.get('line')})"
    )


def _call_fact(index: Any, call: dict[str, Any]) -> dict[str, Any]:
    """The structured form of a call ``_describe_call`` puts in words.

    ``caller`` is the target's code the call is charged to; for a detour
    ``via`` lists the code it went through (outermost first), ``origin_line``
    is the line of the target's code the detour starts at (``None`` for a
    direct call), and ``file`` and ``line`` say where the call itself was made.
    """
    origin, caller = _started_by(call)
    via = (call.get("via") or []) if call.get("origin") else []
    return {
        "kind": "call",
        "case": index,
        "caller": f"{origin}:{caller}",
        "callee": f"{call.get('module')}:{call.get('callee')}",
        "file": call.get("file"),
        "line": call.get("line"),
        "via": [f"{step.get('module')}:{step.get('caller')}" for step in via],
        "origin_line": (call.get("origin") or {}).get("line"),
    }


_WRITE_VERBS = {
    "assigned": "sets",
    "mutated": "changes what is held in",
    "deleted": "deletes",
    "bypassed": "sets, past the class's __setattr__,",
}


def _started_by(call: dict[str, Any]) -> tuple[Any, Any]:
    """The target code a call is charged to: its origin, if made on its behalf."""
    origin = call.get("origin") or {}
    return origin.get("from", call.get("from")), origin.get(
        "caller", call.get("caller")
    )


def _describe_write(write: dict[str, Any]) -> str:
    verb = _WRITE_VERBS.get(str(write.get("change", "assigned")), "sets")
    return (
        f"{write.get('writer')} {verb} {write.get('class')}.{write.get('attribute')} "
        f"at {write.get('file')}:{write.get('line')}"
    )


def _write_fact(index: Any, write: dict[str, Any]) -> dict[str, Any]:
    """The structured form of a write ``_describe_write`` puts in words."""
    return {
        "kind": "write",
        "case": index,
        "change": str(write.get("change", "assigned")),
        "writer": write.get("writer"),
        "class": write.get("class"),
        "attribute": write.get("attribute"),
        "file": write.get("file"),
        "line": write.get("line"),
    }


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


def _raised_note(cases: list[dict[str, Any]]) -> str:
    """Why a pass may hold for part of the code: a case stopped at an exception."""
    raised = next((case for case in cases if case.get("raised")), None)
    if raised is None:
        return ""
    return (
        f"; case {raised.get('index')} raised {raised['raised']}, "
        "so the code after it was not checked"
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
    from pythonarchtesting.dynamic.runner import run_reference_cases

    outcome = run_reference_cases(
        getattr(ctx, "reference_runs", None),
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
    # Reference names of what the target ran, and the reference module the
    # rule's entity belongs to; set by ``evaluate``.
    _names = NameTranslation([])
    _source_module: str | None = None

    def _own(self, module: Any, code: Any) -> bool:
        """Whether ``code`` of the target's ``module`` plays the rule module's part.

        A target that keeps several layers in one module runs the other
        layers' code in the same module; only the entity tells them apart.
        Code no matched entity encloses (a helper the reference lacks) counts
        as the module's own, as it always has.
        """
        if self._source_module is None or module is None:
            return True
        found = self._names.entity_module(str(module), str(code))
        return found is None or found == self._source_module

    def _passes_through(self, item: dict[str, Any], through: list[str]) -> bool:
        """Whether a transitive call or instance came from a ``through`` module."""
        return any(
            _in_module(
                self._names.source_module(
                    str(step.get("module")), str(step.get("caller"))
                ),
                prefix,
            )
            for step in item.get("via") or []
            for prefix in through
        )

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

        self._names = NameTranslation.from_context(ctx)
        self._source_module = source.module_path
        batched = ctx.dynamic_cache.get(cache_key(rule, target))
        details["batched"] = batched is not None
        outcome = batched or run_cases(
            target_root=ctx.target_root,
            module_path=target.module_path,
            qualname=target.qualname,
            kind=target.kind,
            cases=self._names.cases(cases, source, target),
            init=self._names.value(rule.params.get("init"), source, target),
            timeout_s=float(rule.params.get("timeout_s", 5.0)),
            sandbox=ctx.sandbox,
            observe=self._names.observation(observation(rule), source, target),
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
            details.pop("facts", None)
            details["reason"] = "no_violations"
            details["summary"] = (
                self._passed_summary(rule, len(cases))
                + _raised_note(outcome.cases)
                + _coverage_note(coverage)
            )
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
        through = [str(name) for name in rule.params.get("through") or []]
        details["modules"] = modules
        violations: list[str] = []
        # One fact per violation, in the same order (B1 F3).
        facts: list[dict[str, Any]] = []
        for case in cases:
            index = case.get("index")
            calls = [
                call
                for call in case.get("calls") or []
                if self._own(*_started_by(call))
            ]
            if rule.params.get("mode") == "require":
                for module in modules:
                    if not any(self._hits(c, [module]) for c in calls):
                        raised = case.get("raised")
                        suffix = f"; the call raised {raised}" if raised else ""
                        violations.append(
                            f"case {index}: no direct call into "
                            f"{module}{suffix}{_missed_in_case(case)}"
                        )
                        facts.append(
                            {
                                "kind": "missing_call",
                                "case": index,
                                "module": self._names.target_module(module),
                                "reference_module": module,
                                "raised": raised or None,
                            }
                        )
                continue
            for call in calls:
                if self._hits(call, allow) or self._passes_through(call, through):
                    continue
                if self._hits(call, modules):
                    violations.append(f"case {index}: {_describe_call(call)}")
                    facts.append(_call_fact(index, call))
        details["facts"] = facts
        return violations

    def _layer(self, call: dict[str, Any]) -> str:
        """The reference module of the code a recorded call went into."""
        return self._names.source_module(str(call["module"]), str(call.get("callee")))

    def _hits(self, call: dict[str, Any], prefixes: list[str]) -> bool:
        """Whether ``call`` goes into one of ``prefixes``.

        A prefix names a module (``"repository"``) or, dotted, a function of
        one (``"builtins.print"``).
        """
        module = self._layer(call)
        qualified = f"{module}.{call.get('callee')}"
        return any(
            _in_module(module, prefix) or _in_module(qualified, prefix)
            for prefix in prefixes
        )

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
        _ = rule
        found = [
            (case.get("index"), write)
            for case in cases
            for write in case.get("writes") or []
        ]
        details["facts"] = [_write_fact(index, write) for index, write in found]
        return [f"case {index}: {_describe_write(write)}" for index, write in found]

    def _passed_summary(self, rule: Rule, case_count: int) -> str:
        _ = rule
        return f"no foreign attribute writes in {case_count} case(s)"


def _describe_instance(instance: dict[str, Any]) -> str:
    origin = instance.get("origin")
    creator = instance.get("creator")
    if origin:
        # Built by other code while the target ran: name the way there.
        creator = " -> ".join(
            [f"{origin.get('from')}:{origin.get('caller')}"]
            + [f"{step.get('module')}:{step.get('caller')}" for step in instance["via"]]
        )
    return (
        f"{creator} creates {instance.get('module')}:"
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
        through = [str(name) for name in rule.params.get("through") or []]
        own = str(details.get("target_module"))
        violations: list[str] = []
        for case in cases:
            for instance in case.get("instances") or []:
                name = self._names.source_module(
                    str(instance.get("module")), str(instance.get("class"))
                )
                origin = instance.get("origin")
                if origin:
                    # Built by other code on the target's behalf (transitive).
                    if origin.get("from") != own or not self._own(
                        own, origin.get("caller")
                    ):
                        continue
                    if self._passes_through(instance, through):
                        continue
                else:
                    # "creator" is "module:qualname" of the code that built it.
                    creator = str(instance.get("creator") or "").partition(":")[2]
                    if instance.get("from") != own or not self._own(own, creator):
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


def _edges(
    case: dict[str, Any], names: NameTranslation | None = None
) -> dict[tuple[str, str], dict[str, Any]]:
    """First call per ``(from, to)`` module pair, in the order they happened.

    With ``names`` the pair is named by the reference's modules, so a target
    that renamed or merged modules is compared module for module.
    """
    edges: dict[tuple[str, str], dict[str, Any]] = {}
    for call in case.get("calls") or []:
        origin, module = str(call.get("from")), str(call.get("module"))
        if names is not None:
            origin = names.source_module(origin, str(call.get("caller")))
            module = names.source_module(module, str(call.get("callee")))
        if origin == module:
            continue  # within one module: not an edge of the module graph
        edges.setdefault((origin, module), call)
    return edges


def run_edges(
    rule: Rule,
    source: Entity,
    target: Entity,
    ctx: EvalContext,
    details: dict[str, Any],
    observe: dict[str, Any] | None = None,
) -> RuleStatus | tuple[list[dict[str, Any]], list[dict[str, Any]], NameTranslation]:
    """Run the cases on the reference, then on the target, recording edges.

    Every call between two project modules is recorded (``{"calls":
    "edges"}``, or what ``observe`` asks for). Returns the reference's cases,
    the target's cases and the name translation, or the status the rule ends
    with when either side could not run, with ``details`` saying why.
    """
    cases: list[dict[str, Any]] = list(rule.params.get("cases") or [])
    timeout_s = float(rule.params.get("timeout_s", 5.0))
    if ctx.target_root is None or ctx.source_root is None:
        details["reason"] = "dynamic_checks_disabled"
        details["summary"] = "dynamic checks are off; run with --dynamic"
        return "SKIPPED"

    if target.kind not in _SUPPORTED_TARGET_KINDS or target.kind != source.kind:
        details["reason"] = "target_kind_mismatch"
        details["summary"] = f"expected a {source.kind}, matched a {target.kind}"
        return "FAILED"

    from pythonarchtesting.dynamic.runner import run_cases, run_reference_cases

    reference = run_reference_cases(
        getattr(ctx, "reference_runs", None),
        target_root=ctx.source_root,
        module_path=source.module_path,
        qualname=source.qualname,
        kind=source.kind,
        cases=cases,
        init=rule.params.get("init"),
        timeout_s=timeout_s,
        sandbox=ctx.sandbox,
        observe=observe or {"calls": "edges"},
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
        return "ERROR"

    names = NameTranslation.from_context(ctx)
    outcome = run_cases(
        target_root=ctx.target_root,
        module_path=target.module_path,
        qualname=target.qualname,
        kind=target.kind,
        cases=names.cases(cases, source, target),
        init=names.value(rule.params.get("init"), source, target),
        timeout_s=timeout_s,
        sandbox=ctx.sandbox,
        observe=observe or {"calls": "edges"},
    )
    details["probe_status"] = outcome.status
    details["cases"] = outcome.cases
    if outcome.stderr:
        details["stderr_tail"] = outcome.stderr
    if outcome.status != "completed":
        details["reason"] = f"probe_{outcome.status}"
        details["summary"] = f"{outcome.status}: {outcome.error or 'no detail'}"
        return "FAILED"
    broken = [case for case in outcome.cases if case.get("status") == "error"]
    if broken:
        first = broken[0]
        details["reason"] = "case_setup_failed"
        details["summary"] = (
            f"case {first.get('index')} could not run: "
            f"{(first.get('failures') or ['no detail'])[0]}"
        )
        return "FAILED"
    return list(reference.cases), list(outcome.cases), names


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
        require_all = bool(rule.params.get("require_all"))
        allow_new = bool(rule.params.get("allow_new_modules"))
        details: dict[str, Any] = {
            "reason": "",
            "summary": "",
            "case_count": len(cases),
            "require_all": require_all,
        }

        def result(status: Any) -> RuleResult:
            return _build_rule_result(rule, source, target, match, status, details, ())

        observed = run_edges(rule, source, target, ctx, details)
        if isinstance(observed, str):
            return result(observed)
        reference_cases, target_cases, names = observed
        expected = [_edges(case) for case in reference_cases]
        details["reference_edges"] = [
            sorted(f"{a} -> {b}" for a, b in edges) for edges in expected
        ]

        # Reflexion-model terms: a divergence is a call the reference does not
        # make, an absence a call of the reference the target does not make.
        divergences: list[str] = []
        absences: list[str] = []
        # Modules of the reference, which new modules of the target fold into.
        known = (
            {str(entity.module_path) for entity in ctx.source_by_id.values()}
            if allow_new
            else set()
        )
        for case, allowed in zip(target_cases, expected):
            index = case.get("index")
            actual = _edges(case, names)
            if allow_new:
                actual = fold_new_modules(actual, known)[0]
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
        coverage = _coverage(target_cases)
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
        types = dict(rule.params.get("types") or {})
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
                elif require and name in types and not member.get("type_ok"):
                    held = member.get("type_error") or f"a {member.get('type')}"
                    violations.append(
                        f"case {index}: {name!r} is {held}, not an instance of "
                        f"{types[name]}"
                    )
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
