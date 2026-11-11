from __future__ import annotations

from typing import Any

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult
from pythonarchtesting.dynamic.translation import NameTranslation
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult

from .messages import build_rule_result


def _describe(hit: dict[str, Any]) -> str:
    return f"{hit.get('module')} at {hit.get('file')}:{hit.get('line')}"


class RuntimeImportsEvaluator:
    """Evaluator for ``forbid_runtime_imports`` rules.

    It imports the matched target module in a child interpreter and fails on any
    forbidden import the target's own code performed meanwhile. Like
    the other runtime evaluators it only runs when ``ctx.target_root`` is set.
    """

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        forbidden = [str(name) for name in rule.params.get("forbidden") or []]
        details: dict[str, Any] = {
            "reason": "",
            "summary": "",
            "forbidden": forbidden,
            "allow": list(rule.params.get("allow") or []),
            "violations": [],
        }

        if ctx.target_root is None:
            details["reason"] = "dynamic_checks_disabled"
            details["summary"] = "dynamic checks are off; run with --dynamic"
            return build_rule_result(
                rule, source, target, match, "SKIPPED", details, ()
            )

        if target.kind != "module":
            details["reason"] = "target_kind_mismatch"
            details["summary"] = f"expected a module, matched a {target.kind}"
            return build_rule_result(rule, source, target, match, "FAILED", details, ())

        from pythonarchtesting.dynamic.runner import run_import_check

        # The probe filters by name, so project modules are sent under the
        # names the target gave them.
        names = NameTranslation.from_context(ctx)
        outcome = run_import_check(
            target_root=ctx.target_root,
            module_path=target.module_path,
            forbidden=[
                mapped for name in forbidden for mapped in names.target_modules(name)
            ],
            allow=[
                mapped
                for name in details["allow"]
                for mapped in names.target_modules(name)
            ],
            timeout_s=float(rule.params.get("timeout_s", 5.0)),
            sandbox=ctx.sandbox,
        )
        details["probe_status"] = outcome.status
        details["violations"] = outcome.imports
        if outcome.error:
            details["error"] = outcome.error
        if outcome.stderr:
            details["stderr_tail"] = outcome.stderr

        if outcome.status != "completed":
            details["reason"] = f"probe_{outcome.status}"
            details["summary"] = f"{outcome.status}: {outcome.error or 'no detail'}"
            return build_rule_result(rule, source, target, match, "FAILED", details, ())

        if not outcome.imports:
            details["reason"] = "no_forbidden_imports"
            details["summary"] = "no forbidden module was imported"
            return build_rule_result(rule, source, target, match, "OK", details, ())

        details["reason"] = "forbidden_import_executed"
        details["summary"] = "imported " + "; ".join(
            _describe(hit) for hit in outcome.imports
        )
        return build_rule_result(rule, source, target, match, "FAILED", details, ())


__all__ = ["RuntimeImportsEvaluator"]
