"""Run the call and write rules of one target module in a single interpreter.

Starting a fresh interpreter per rule costs start-up and a full import of the
target each time. Before a target's rules are evaluated, ``prefetch`` groups
the matched rules of the types in ``_BATCHED_RULE_TYPES`` (runtime calls,
writes, instances, members, class kinds, protocols and patterns) by target
module, runs each group as one batch, and leaves the outcomes in
``EvalContext.dynamic_cache``; the evaluator then reads its outcome from there.

Rules of one module share the module's state in the batch, just as the cases
of one rule always have. When a batch as a whole times out or crashes, its
rules are left out of the cache and each runs in its own interpreter, so the
verdicts stay attributable to the rule that caused the problem.

Where the probe can fork (``runner.can_fork``), one interpreter serves the
whole target: each module's batch, and the probe of a rule alone on its
module, runs in a fork of its own, which sees the target as freshly imported
as a probe of its own would. The outcome of a rule alone is left under
``solo_key`` of its request, so the evaluator takes it in place of starting
the same probe itself; it is still no batch (``details["batched"]``).
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from pythonarchtesting.dynamic.runner import (
    ProbeOutcome,
    batch_request,
    batch_timeout,
    can_fork,
    cases_request,
    run_case_batch,
    run_forked,
)
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


# Builtins of no layer a rule may still name (``builtins.isinstance``): the
# probe records a call of one only when asked (``observe.builtins``).
WATCHABLE_BUILTINS = ("isinstance", "type")


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
    calls: dict[str, Any] = {
        "calls": "transitive" if rule.params.get("transitive") else True
    }
    # isinstance() and type() belong to no layer and are recorded only when
    # the rule names them: they run often and would only grow the report.
    watched = [
        name
        for name in WATCHABLE_BUILTINS
        if f"builtins.{name}" in (rule.params.get("modules") or [])
    ]
    if watched:
        calls["builtins"] = watched
    return calls


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


def solo_key(
    *,
    module_path: str,
    qualname: str,
    kind: str,
    cases: list[dict[str, Any]],
    init: Any,
    timeout_s: float,
    observe: dict[str, Any],
) -> tuple[str, str, str]:
    """The ``ctx.dynamic_cache`` key of the outcome of one rule's own probe:
    its whole request, so an evaluator that would send another one misses."""
    request = cases_request(
        module_path=module_path,
        qualname=qualname,
        kind=kind,
        cases=cases,
        init=init,
        observe=observe,
    )
    text = json.dumps([request, float(timeout_s)], sort_keys=True, default=str)
    return ("", "run_cases", text)


_Entry = tuple[tuple[str, str, str], dict[str, Any]]


def prefetch(rules: Iterable[Any], ctx: Any) -> None:
    """Fill ``ctx.dynamic_cache`` for every module with two or more rules,
    and, where one interpreter can serve them all, for every other rule too."""
    groups: dict[str, list[_Entry]] = {}
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

    sandbox = getattr(ctx, "sandbox", None)
    batches = {path: entries for path, entries in groups.items() if len(entries) > 1}
    alone = {path: entries[0] for path, entries in groups.items() if len(entries) == 1}
    forked: dict[str, ProbeOutcome | None] = {}
    if len(groups) > 1 and can_fork(sandbox):
        forked = _run_forked(ctx, batches, alone)

    for module_path, entries in batches.items():
        outcome = forked.get(module_path) or run_case_batch(
            target_root=ctx.target_root,
            module_path=module_path,
            jobs=[job for _, job in entries],
            sandbox=sandbox,
        )
        _cache_batch(ctx, entries, outcome)


def _solo_fields(module_path: str, job: dict[str, Any]) -> dict[str, Any]:
    """The arguments ``run_cases`` gets for the rule of ``job`` alone."""
    return {
        "module_path": module_path,
        **{
            name: job[name]
            for name in ("qualname", "kind", "cases", "init", "timeout_s", "observe")
        },
    }


def _run_forked(
    ctx: Any, batches: dict[str, list[_Entry]], alone: dict[str, _Entry]
) -> dict[str, ProbeOutcome | None]:
    """Run every batch and every rule alone on its module from one
    interpreter (``runner.run_forked``): leave the outcomes of the rules
    alone in ``ctx.dynamic_cache`` under ``solo_key`` and return the
    batches' (``None``: not run)."""
    requests: list[tuple[dict[str, Any], float]] = []
    for module_path, entries in batches.items():
        jobs = [job for _, job in entries]
        requests.append((batch_request(module_path, jobs), batch_timeout(jobs)))
    keys = []
    for module_path, (_, job) in alone.items():
        fields = _solo_fields(module_path, job)
        keys.append(solo_key(**fields))
        timeout_s = float(fields.pop("timeout_s"))
        requests.append((cases_request(**fields), timeout_s))
    outcomes = run_forked(
        target_root=ctx.target_root,
        requests=requests,
        sandbox=getattr(ctx, "sandbox", None),
    )
    for key, outcome in zip(keys, outcomes[len(batches) :]):
        if outcome is not None:
            ctx.dynamic_cache[key] = outcome
    return dict(zip(batches, outcomes[: len(batches)]))


def _cache_batch(ctx: Any, entries: list[_Entry], outcome: ProbeOutcome) -> None:
    """Leave each rule's outcome of its module's batch in ``ctx.dynamic_cache``."""
    if outcome.status == "import_error":
        # Every rule on this module would hit the same import failure.
        for key, _ in entries:
            ctx.dynamic_cache[key] = ProbeOutcome(
                status="import_error", error=outcome.error, stderr=outcome.stderr
            )
        return
    if outcome.status != "completed":
        return
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


__all__ = ["cache_key", "observation", "prefetch", "solo_key"]
