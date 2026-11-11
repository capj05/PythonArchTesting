from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.architecture.compare import fold_new_modules
from pythonarchtesting.core.models import EvalContext, Rule, RuleResult, RuleStatus
from pythonarchtesting.dynamic.translation import NameTranslation
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult
from pythonarchtesting.util.ast_utils import kept_names

from .messages import build_rule_result
from .type_tests import TypeTests

_SUPPORTED_TARGET_KINDS = frozenset({"function", "method"})


def _in_module(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def describe_call(call: dict[str, Any]) -> str:
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
    """The structured form of a call ``describe_call`` puts in words.

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


# The builtins a static check (``cover_module``) recognises by their bare
# name or as ``builtins.x`` / ``io.open``, as (module, name) the probe
# records them under.
_STATIC_BUILTINS = {
    "print": ("builtins", "print"),
    "input": ("builtins", "input"),
    "open": ("io", "open"),
    "builtins.print": ("builtins", "print"),
    "builtins.input": ("builtins", "input"),
    "builtins.open": ("io", "open"),
    "io.open": ("io", "open"),
}


def _static_callee(func: ast.expr) -> Optional[str]:
    """``print`` of ``print(...)``, ``io.open`` of ``io.open(...)``."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return f"{func.value.id}.{func.attr}"
    return None


def _rebound_names(tree: ast.AST) -> set[str]:
    """The names a module binds anywhere: by an import, a ``def`` or
    ``class``, an assignment or a parameter. A bare ``print`` of such a module
    may not be the builtin (``from rich import print``), so the static check
    does not take it for one; the set errs on the side of names bound only
    locally."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(
                alias.asname or alias.name.split(".")[0] for alias in node.names
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    return names


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
    held = f" (held in {write['held_by']})" if write.get("held_by") else ""
    return (
        f"{write.get('writer')} {verb} {write.get('class')}.{write.get('attribute')}"
        f"{held} at {write.get('file')}:{write.get('line')}"
    )


def _write_fact(index: Any, write: dict[str, Any]) -> dict[str, Any]:
    """The structured form of a write ``_describe_write`` puts in words.

    ``held_by`` names the module global (``world.BAG``) that held the object,
    itself or inside it, when the case started, for an object the case
    reached only through it; a write to an argument has none. It is no
    detour (``via``): the write is the function's own."""
    fact = {
        "kind": "write",
        "case": index,
        "change": str(write.get("change", "assigned")),
        "writer": write.get("writer"),
        "class": write.get("class"),
        "attribute": write.get("attribute"),
        "file": write.get("file"),
        "line": write.get("line"),
    }
    if write.get("held_by"):
        fact["held_by"] = write["held_by"]
    return fact


def line_ranges(lines: list[int]) -> str:
    """``[3, 4, 5, 9]`` as ``"3-5, 9"``."""
    spans: list[list[int]] = []
    for line in sorted(lines):
        if spans and line == spans[-1][1] + 1:
            spans[-1][1] = line
        else:
            spans.append([line, line])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in spans)


def case_coverage(cases: list[dict[str, Any]]) -> dict[str, Any] | None:
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


def coverage_note(coverage: dict[str, Any] | None) -> str:
    if not coverage or not coverage["unexercised_lines"]:
        return ""
    return (
        f"; no case ran lines {line_ranges(coverage['unexercised_lines'])} "
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


def _unobserved_note(details: dict[str, Any]) -> str:
    """Which calls the rule names could not be seen, and why."""
    unobserved = details.get("unobserved_calls") or {}
    if not unobserved:
        return ""
    return "; not observable: " + ", ".join(
        f"{name}() ({why})" for name, why in unobserved.items()
    )


def _missed_in_case(case: dict[str, Any]) -> str:
    """Why a call may be absent: the code that would make it did not run."""
    missed = (case.get("lines") or {}).get("missed") or []
    if not missed:
        return ""
    return f"; lines {line_ranges(missed)} did not run in this case"


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
    _target_name: str = ""
    _target_file: str | None = None
    _target_module: str = ""
    # ``module.Class`` of every class of the reference; set by ``evaluate``.
    _reference_classes: frozenset[str] = frozenset()
    _source_by_id: dict[str, Any] = {}

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
            return build_rule_result(
                rule, source, target, match, "SKIPPED", details, ()
            )

        if target.kind not in self.supported_kinds or target.kind != source.kind:
            details["reason"] = "target_kind_mismatch"
            details["summary"] = f"expected a {source.kind}, matched a {target.kind}"
            return build_rule_result(rule, source, target, match, "FAILED", details, ())

        from pythonarchtesting.dynamic.batch import cache_key, observation, solo_key
        from pythonarchtesting.dynamic.runner import run_cases

        self._names = NameTranslation.from_context(ctx)
        self._source_by_id = getattr(ctx, "source_by_id", None) or {}
        self._reference_classes = frozenset(
            f"{entity.module_path}.{entity.qualname}"
            for entity in self._source_by_id.values()
            if getattr(entity, "kind", None) == "class"
        )
        self._target_root = ctx.target_root
        self._source_module = source.module_path
        self._target_name = f"{target.module_path}:{target.qualname}"
        self._target_file = str(target.filepath_rel)
        self._target_module = str(target.module_path)
        batched = ctx.dynamic_cache.get(cache_key(rule, target))
        details["batched"] = batched is not None
        request: dict[str, Any] = {
            "module_path": target.module_path,
            "qualname": target.qualname,
            "kind": target.kind,
            "cases": self._names.cases(cases, source, target),
            "init": self._names.value(rule.params.get("init"), source, target),
            "timeout_s": float(rule.params.get("timeout_s", 5.0)),
            "observe": self._names.observation(observation(rule), source, target),
        }
        # The probe of this rule alone may have run already, forked from the
        # interpreter that served the target's batches (``batch.prefetch``).
        outcome = (
            batched
            or ctx.dynamic_cache.pop(solo_key(**request), None)
            or run_cases(target_root=ctx.target_root, sandbox=ctx.sandbox, **request)
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
            return build_rule_result(rule, source, target, match, "FAILED", details, ())
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
                return build_rule_result(
                    rule, source, target, match, "ERROR", details, ()
                )
            details["reason"] = "case_setup_failed"
            details["summary"] = f"case {first.get('index')} could not run: {failure}"
            return build_rule_result(rule, source, target, match, "FAILED", details, ())

        details["target_module"] = target.module_path
        coverage = case_coverage(outcome.cases)
        if coverage is not None:
            details["coverage"] = coverage
        violations = self._violations(rule, outcome.cases, details)
        if not violations:
            details.pop("facts", None)
            details["reason"] = "no_violations"
            details["summary"] = (
                self._passed_summary(rule, len(cases))
                + _raised_note(outcome.cases)
                + coverage_note(coverage)
                + _unobserved_note(details)
            )
            return build_rule_result(rule, source, target, match, "OK", details, ())
        details["violations"] = violations
        details["reason"] = "violation"
        more = f" (+{len(violations) - 1} more)" if len(violations) > 1 else ""
        details["summary"] = violations[0] + more
        return build_rule_result(rule, source, target, match, "FAILED", details, ())


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
        # A call of isinstance or type counts only where it tests a type.
        root = getattr(self, "_target_root", None)
        type_tests = TypeTests(Path(root) if root is not None else None)
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
                if self._hits(call, modules) and type_tests.is_type_test(
                    f"{call.get('module')}:{call.get('callee')}",
                    call.get("file"),
                    call.get("line"),
                ):
                    violations.append(f"case {index}: {describe_call(call)}")
                    facts.append(_call_fact(index, call))
        if rule.params.get("cover_module") and rule.params.get("mode") != "require":
            for fact in self._uncovered_calls(modules, allow):
                violations.append(
                    f"static: {fact['caller']} calls {fact['callee']} (line "
                    f"{fact['line']}), in a function no reference entity matches"
                )
                facts.append(fact)
        details["facts"] = facts
        unobserved: dict[str, str] = {}
        for case in cases:
            unobserved.update(case.get("unobserved") or {})
        if unobserved:
            # The cases ran, but some calls the rule names could not be seen
            # on this interpreter: the verdict holds without them.
            details["unobserved_calls"] = dict(sorted(unobserved.items()))
        return violations

    def _uncovered_calls(
        self, modules: list[str], allow: list[str]
    ) -> list[dict[str, Any]]:
        """``cover_module``: the calls of a builtin the rule forbids
        (``print``, ``input``, ``open``) in the body of each top-level public
        function of the target's module that no reference entity matches,
        as static facts. No case runs such a function, so only its own body
        is read: a call it makes through a helper of another module is not
        seen, nor a method of a class the target adds. A bare name the module
        rebinds (``from rich import print``) is not the builtin."""
        root = getattr(self, "_target_root", None)
        if root is None or not self._target_file:
            return []
        try:
            tree = ast.parse(
                (Path(root) / self._target_file).read_text(encoding="utf-8")
            )
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
            return []
        module = self._target_module
        rebound = _rebound_names(tree)
        facts: list[dict[str, Any]] = []
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_") or self._names.source_name(module, node.name):
                continue
            for call in sorted(
                (n for n in ast.walk(node) if isinstance(n, ast.Call)),
                key=lambda n: (n.lineno, n.col_offset),
            ):
                name = _static_callee(call.func) or ""
                callee = _STATIC_BUILTINS.get(name)
                if callee is None or name in rebound:
                    continue
                qualified = ".".join(callee)
                if any(_in_module(qualified, prefix) for prefix in allow) or not any(
                    _in_module(qualified, prefix) for prefix in modules
                ):
                    continue
                facts.append(
                    {
                        "kind": "call",
                        "case": None,
                        "caller": f"{module}:{node.name}",
                        "callee": ":".join(callee),
                        "file": self._target_file,
                        "line": call.lineno,
                        "via": [],
                        "origin_line": None,
                        "static": True,
                        "function_line": node.lineno,
                    }
                )
        return facts

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


def _instance_fact(index: Any, instance: dict[str, Any]) -> dict[str, Any]:
    """The structured form of an instance ``_describe_instance`` puts in words.

    ``creator`` is the target's code the object is charged to; for one built
    by other code on its behalf ``via`` lists that code (outermost first), and
    ``file`` and ``line`` say where the object itself was built.
    """
    origin = instance.get("origin")
    creator = (
        f"{origin.get('from')}:{origin.get('caller')}"
        if origin
        else instance.get("creator")
    )
    via = (instance.get("via") or []) if origin else []
    return {
        "kind": "instance",
        "case": index,
        "creator": creator,
        "class": f"{instance.get('module')}:{instance.get('class')}",
        "file": instance.get("file"),
        "line": instance.get("line"),
        "via": [f"{step.get('module')}:{step.get('caller')}" for step in via],
    }


class RuntimeInstancesEvaluator(_ObservingEvaluator):
    """Evaluator for ``forbid_runtime_instantiation``.

    The probe reports every project class instantiated by project code; only
    objects created by code of the target's own module count here. A name in
    ``modules`` is a module (each of its classes counts) or a class
    (``module.Class``, by its name in the reference). A class the target
    builds that no reference class matches (a renamed one, or one of its
    own) counts when it lives in the module of a class ``modules`` names and
    looks like one of them: it has one of them or one of their reference
    bases (the interface) among its bases, or defines a public method of the
    same name as one of theirs (``apply``). The reference cannot name it; a
    class of the module that is no such class (a value ``Money``, a
    dataclass, an exception) and a matched class the rule does not name (a
    ``Log`` beside the strategies) stay allowed.
    """

    def _violations(
        self, rule: Rule, cases: list[dict[str, Any]], details: dict[str, Any]
    ) -> list[str]:
        modules = [str(name) for name in rule.params.get("modules") or []]
        allow = [str(name) for name in rule.params.get("allow") or []]
        through = [str(name) for name in rule.params.get("through") or []]
        own = str(details.get("target_module"))
        # The modules of the classes ``modules`` names, for a target's class
        # the reference has no counterpart of.
        class_modules = {
            name.rpartition(".")[0]
            for name in modules
            if name in self._reference_classes
        }
        kin, methods = self._class_kin(
            [name for name in modules if name in self._reference_classes]
        )
        violations: list[str] = []
        # One fact per violation, in the same order.
        facts: list[dict[str, Any]] = []
        for case in cases:
            for instance in case.get("instances") or []:
                module, cls = str(instance.get("module")), str(instance.get("class"))
                name = self._names.source_module(module, cls)
                # The class by its reference name: a target may name a class.
                source = self._names.source_name(module, cls)
                full = ".".join(source) if source else f"{name}.{cls}"
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
                if any(_in_module(full, prefix) for prefix in modules) or (
                    source is None
                    and name in class_modules
                    and self._looks_like(instance, kin, methods)
                ):
                    violations.append(
                        f"case {case.get('index')}: {_describe_instance(instance)}"
                    )
                    facts.append(_instance_fact(case.get("index"), instance))
        details["facts"] = facts
        return violations

    def _class_kin(self, classes: list[str]) -> tuple[set[str], set[str]]:
        """The reference classes ``classes`` names with their reference
        bases, and the public methods those define."""
        entities = list((getattr(self, "_source_by_id", None) or {}).values())
        by_name = {
            f"{e.module_path}.{e.qualname}": e
            for e in entities
            if getattr(e, "kind", None) == "class"
        }
        kin: set[str] = set()
        todo = list(classes)
        while todo:
            name = todo.pop()
            if name in kin or name not in by_name:
                continue
            kin.add(name)
            todo.extend(str(b) for b in (by_name[name].extras or {}).get("bases") or [])
        methods = {
            e.qualname.rpartition(".")[2]
            for e in entities
            if getattr(e, "kind", None) == "method"
            and f"{e.module_path}.{e.qualname.rpartition('.')[0]}" in kin
            and not e.qualname.rpartition(".")[2].startswith("_")
        }
        return kin, methods

    def _looks_like(
        self, instance: dict[str, Any], kin: set[str], methods: set[str]
    ) -> bool:
        """Whether a built class no reference class matches is one of
        ``kin`` (by a base) or shares a public method with them; an exception
        never is."""
        if instance.get("exception"):
            return False
        for module, qualname in instance.get("bases") or []:
            source = self._names.source_name(str(module), str(qualname))
            full = (
                ".".join(source)
                if source
                else f"{self._names.source_module(str(module), str(qualname))}.{qualname}"
            )
            if full in kin:
                return True
        return bool(methods & set(instance.get("methods") or []))

    def _passed_summary(self, rule: Rule, case_count: int) -> str:
        modules = ", ".join(rule.params.get("modules") or [])
        return f"no instance of {modules} created in {case_count} case(s)"


def case_edges(
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
            return build_rule_result(rule, source, target, match, status, details, ())

        observed = run_edges(rule, source, target, ctx, details)
        if isinstance(observed, str):
            return result(observed)
        reference_cases, target_cases, names = observed
        expected = [case_edges(case) for case in reference_cases]
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
            actual = case_edges(case, names)
            if allow_new:
                actual = fold_new_modules(actual, known)[0]
            for (origin, module), call in actual.items():
                if (origin, module) not in allowed:
                    divergences.append(
                        f"case {index}: {origin} -> {module} is not in the "
                        f"reference ({describe_call(call)})"
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
        coverage = case_coverage(target_cases)
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
                + coverage_note(coverage)
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


def spy_holder(tree: ast.Module, owner: str, init: Any, spy: str) -> Optional[str]:
    """What the constructor of class ``owner`` (its qualname) keeps the spy
    named ``spy`` in, given ``init`` (``{"args": [...], "kwargs": {...}}``):
    ``self.x`` for ``self.x = p`` (or ``self.x: T = p``), else the parameter
    ``p`` itself; ``None`` when the class, its ``__init__`` or the spy is not
    found."""
    if not isinstance(init, dict):
        return None
    body: list[ast.stmt] = tree.body
    cls: Optional[ast.ClassDef] = None
    for part in owner.split("."):
        cls = next(
            (n for n in body if isinstance(n, ast.ClassDef) and n.name == part), None
        )
        if cls is None:
            return None
        body = cls.body
    constructor = next(
        (
            n
            for n in body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == "__init__"
        ),
        None,
    )
    if constructor is None:
        return None
    positional = [a.arg for a in constructor.args.posonlyargs + constructor.args.args]
    if not positional:
        return None
    self_name, names = positional[0], positional[1:]

    def is_spy(value: Any) -> bool:
        return isinstance(value, dict) and value.get("$spy") == spy

    given = list(zip(names, init.get("args") or []))
    given += list((init.get("kwargs") or {}).items())
    param = next((name for name, value in given if is_spy(value)), None)
    if param is None:
        return None
    # ``kept_names`` takes ``self`` as the constructor's first parameter too.
    for _, attribute, value in kept_names(constructor):
        if value.id == param:
            return f"{self_name}.{attribute}"
    return str(param)


def _delegation_violations(
    rule: Rule,
    case: dict[str, Any],
    caller: str,
    facts: list[dict[str, Any]],
    holder: Optional[str] = None,
) -> list[str]:
    """The case's violation, if it never delegated; its fact (``caller`` is
    the target as ``module:qualname``) is appended to ``facts``. Its
    ``expected`` names where the target keeps the spy (``holder``, such as
    ``self.discount``), else the spy."""
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
    facts.append(
        {
            "kind": "missing_delegation",
            "case": case.get("index"),
            "caller": caller,
            "expected": f"{holder or spy}.{member}" if member else holder or spy,
            "raised": raised or None,
        }
    )
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
        pattern = rule.params.get("pattern")
        violations: list[str] = []
        facts: list[dict[str, Any]] = []
        holder = (
            self._spy_holder(rule) if pattern not in ("singleton", "observer") else None
        )
        for case in cases:
            if pattern == "singleton":
                violations.extend(_singleton_violations(case))
            elif pattern == "observer":
                violations.extend(_observer_violations(rule, case))
            else:
                violations.extend(
                    _delegation_violations(rule, case, self._target_name, facts, holder)
                )
        if pattern not in ("singleton", "observer"):
            # Only delegation reports facts (one per violation).
            details["facts"] = facts
        return violations

    def _spy_holder(self, rule: Rule) -> Optional[str]:
        """Where the target's constructor keeps the spy (``spy_holder``), read
        from the target's code; ``None`` when it cannot be told."""
        root = getattr(self, "_target_root", None)
        qualname = self._target_name.partition(":")[2]
        owner = qualname.rpartition(".")[0]
        file = self._target_file
        if root is None or not owner or not file:
            return None
        try:
            tree = ast.parse((Path(root) / str(file)).read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
            return None
        return spy_holder(
            tree, owner, rule.params.get("init"), str(rule.params.get("spy"))
        )

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
    "case_coverage",
    "coverage_note",
    "describe_call",
    "case_edges",
    "line_ranges",
]
