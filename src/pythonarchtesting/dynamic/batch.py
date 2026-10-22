"""Run the call and write rules of one target module in a single interpreter.

Starting a fresh interpreter per rule costs start-up and a full import of the
target each time. Before a target's rules are evaluated, ``prefetch`` groups
the matched ``forbid_runtime_calls``, ``require_runtime_calls``,
``forbid_foreign_writes`` and ``forbid_runtime_instantiation`` rules by target
module, runs each group as one
batch, and leaves the outcomes in ``EvalContext.dynamic_cache``; the evaluator
then reads its outcome from there.

Rules of one module share the module's state in the batch, just as the cases
of one rule always have. When a batch as a whole times out or crashes, its
rules are left out of the cache and each runs in its own interpreter, so the
verdicts stay attributable to the rule that caused the problem.
"""

from __future__ import annotations

from typing import Any, Iterable

from pythonarchtesting.dynamic.runner import ProbeOutcome, run_case_batch
from pythonarchtesting.dynamic.translation import NameTranslation

_BATCHED_RULE_TYPES = frozenset(
    {
        "runtime_calls",
        "runtime_writes",
        "runtime_instances",
        "runtime_members",
        "runtime_class_kind",
        "runtime_protocol",
        "runtime_pattern",
    }
)
_SUPPORTED_KINDS = frozenset({"function", "method", "class"})


def _pattern_observation(params: dict[str, Any]) -> dict[str, Any]:
    pattern = params.get("pattern")
    if pattern == "singleton":
        return {"construct": False, "singleton": {"access": params.get("access")}}
    if pattern == "observer":
        keys = ("subscribe", "notify", "unsubscribe", "notify_args", "subscribe_args")
        return {"observer": {key: params.get(key) for key in keys}}
    return {"spies": True}


def observation(rule: Any) -> dict[str, Any]:
    """What the probe has to record for ``rule``."""
    if rule.rule_type == "runtime_writes":
        return {"writes": True}
    if rule.rule_type == "runtime_instances":
        return {"instances": "transitive" if rule.params.get("transitive") else True}
    if rule.rule_type == "runtime_members":
        observe: dict[str, Any] = {"names": list(rule.params.get("names") or [])}
        if rule.params.get("types"):
            observe["types"] = dict(rule.params["types"])
        return observe
    if rule.rule_type == "runtime_class_kind":
        return {"construct": rule.params.get("expect") == "concrete"}
    if rule.rule_type == "runtime_pattern":
        return _pattern_observation(rule.params)
    if rule.rule_type == "runtime_protocol":
        return {
            "names": list(rule.params.get("attributes") or []),
            "callables": dict(rule.params.get("methods") or {}),
        }
    if rule.params.get("transitive"):
        return {"calls": "transitive"}
    return {"calls": True}


def cache_key(rule: Any, target: Any) -> tuple[str, str, str]:
    return (rule.rule_id, rule.selector.source_entity_id, target.canonical_id)


def _batchable(rule: Any, ctx: Any) -> tuple[Any, Any] | None:
    from pythonarchtesting.matching import MatchStatus

    if not rule.enabled or rule.rule_type not in _BATCHED_RULE_TYPES:
        return None
    source = ctx.source_by_id.get(rule.selector.source_entity_id)
    match = ctx.matches.get(rule.selector.source_entity_id)
    if source is None or match is None or match.status != MatchStatus.MATCHED:
        return None
    target = ctx.target_by_id.get(match.target_id) if match.target_id else None
    if target is None or target.kind not in _SUPPORTED_KINDS:
        return None
    if target.kind != source.kind:
        return None
    return source, target


def prefetch(rules: Iterable[Any], ctx: Any) -> None:
    """Fill ``ctx.dynamic_cache`` for every module with two or more rules."""
    groups: dict[str, list[tuple[tuple[str, str, str], dict[str, Any]]]] = {}
    names = NameTranslation.from_context(ctx)
    for rule in rules:
        pair = _batchable(rule, ctx)
        if pair is None:
            continue
        source, target = pair
        entries = groups.setdefault(target.module_path, [])
        job = {
            "id": str(len(entries)),
            "qualname": target.qualname,
            "kind": target.kind,
            "cases": names.cases(list(rule.params.get("cases") or []), source, target),
            "init": names.value(rule.params.get("init"), source, target),
            "timeout_s": float(rule.params.get("timeout_s", 5.0)),
            "observe": names.observation(observation(rule), source, target),
        }
        entries.append((cache_key(rule, target), job))

    for module_path, entries in groups.items():
        if len(entries) < 2:
            continue  # one rule gains nothing from a batch
        outcome = run_case_batch(
            target_root=ctx.target_root,
            module_path=module_path,
            jobs=[job for _, job in entries],
            sandbox=getattr(ctx, "sandbox", None),
        )
        if outcome.status == "import_error":
            # Every rule on this module would hit the same import failure.
            for key, _ in entries:
                ctx.dynamic_cache[key] = ProbeOutcome(
                    status="import_error", error=outcome.error, stderr=outcome.stderr
                )
            continue
        if outcome.status != "completed":
            continue
        for key, job in entries:
            result = outcome.jobs.get(job["id"])
            if result is None:
                continue
            ctx.dynamic_cache[key] = ProbeOutcome(
                status=str(result.get("status", "crashed")),
                cases=list(result.get("cases") or []),
                error=result.get("error"),
                # Each job's output is captured on its own in the child.
                stderr=str(result.get("stderr") or ""),
            )


__all__ = ["cache_key", "observation", "prefetch"]
