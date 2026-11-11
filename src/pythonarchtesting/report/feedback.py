"""What a client needs to explain one result of a JSON report.

``feedback`` gives the rule, its summary and fix hints and the issues one by
one; ``explain_result`` adds the result's place, evidence and reason. A
client writes the explanation for a student from these; the tool never does.
A result whose ``details`` is not an object raises ``TypeError``.
"""

from __future__ import annotations

from typing import Any

EVIDENCE_CAP = 5
_NOT_PROBLEMS = ("OK", "SKIPPED")


def rule_key(result: dict[str, Any]) -> str:
    """Identify a result; one rule_id can sit on several entities."""
    qualname = result["locations"]["source"]["qualname"]
    return f"{result['rule_id']}@{qualname}"


def is_problem(result: dict[str, Any]) -> bool:
    """Whether the result is neither passed nor skipped."""
    return result["status"] not in _NOT_PROBLEMS


def result_details(result: dict[str, Any]) -> dict[str, Any]:
    """The result's ``details`` (empty without); ``TypeError`` when they are
    not an object."""
    details = result.get("details") or {}
    if not isinstance(details, dict):
        raise TypeError(f"details must be an object, not {type(details).__name__}")
    return details


def _step_issue(
    kind: str, edge: str, path: list[str], steps: list[dict[str, Any]]
) -> dict[str, Any]:
    first = steps[0] if steps else {}
    return {
        "kind": kind,
        "edge": edge,
        "path": path,
        "file": first.get("filepath"),
        "line": first.get("lineno"),
    }


def _reference_allows(
    details: dict[str, Any], layer: str, module: str | None
) -> list[str]:
    """The reference's edges of ``layer`` that start in ``module``."""
    diff = (details.get("architecture") or {}).get(layer) or {}
    edges = (
        set(diff.get("convergent") or [])
        | set(diff.get("absent") or [])
        | set(diff.get("allowed") or [])
    )
    return sorted(edge for edge in edges if module and edge.split(" -> ")[0] == module)


def _divergence_issues(details: dict[str, Any]) -> list[dict[str, Any]]:
    """Each divergence from the reference model, with what the reference's
    module does instead."""
    issues = []
    for divergence in details.get("divergences") or []:
        issue = dict(divergence)
        layer = str(divergence.get("layer"))
        if layer != "external":
            # A library the reference uses is allowed from any module, so a
            # per-module list would mislead; the other layers have one.
            origin = str(divergence.get("edge", "")).split(" -> ")[0]
            issue["reference_allows"] = _reference_allows(details, layer, origin)
        issues.append(issue)
    return issues


def _path_issues(details: dict[str, Any]) -> list[dict[str, Any]]:
    """Each forbidden path, from its first module to its last."""
    issues = []
    for path in details.get("paths") or []:
        steps = list(path.get("steps") or [])
        modules = [steps[0]["from"], *(step["to"] for step in steps)] if steps else []
        issues.append(
            _step_issue(
                str(path.get("kind") or "violation"),
                f"{modules[0]} -> {modules[-1]}" if modules else "",
                modules,
                steps,
            )
        )
    return issues


def _cycle_issues(details: dict[str, Any]) -> list[dict[str, Any]]:
    """Each import cycle."""
    issues = []
    for cycle in details.get("cycles") or []:
        route = list(cycle.get("path") or [])
        issues.append(
            _step_issue(
                "cycle", " -> ".join(route), route, list(cycle.get("steps") or [])
            )
        )
    return issues


def _text_issues(result: dict[str, Any], details: dict[str, Any]) -> list[Any]:
    """Without structured issues: each fact of a runtime rule with the
    violation text it states, else each violation text (or the summary)."""
    facts = list(details.get("facts") or [])
    texts = list(details.get("violations") or [])
    if facts and len(facts) == len(texts):
        # Runtime rules (B1 F3): each fact with the violation text it states.
        return [{**fact, "text": str(text)} for fact, text in zip(facts, texts)]
    if not texts and (details.get("summary") or result.get("message")):
        texts = [details.get("summary") or result.get("message")]
    return [{"kind": "violation", "text": str(text)} for text in texts]


def feedback(result: dict[str, Any]) -> dict[str, Any]:
    """What a client needs to explain one result to a student.

    The rule, its summary and fix hints, and the issues one by one: the edge
    (or path, or cycle), where the target makes it, and for the reference
    model what the reference's module does instead. A client writes the
    explanation from this; the server never does.
    """
    details = result_details(result)
    issues = [
        *_divergence_issues(details),
        *_path_issues(details),
        *_cycle_issues(details),
    ]
    if not issues:
        issues = _text_issues(result, details)
    parts = str(result.get("rule_id", "")).split("/")
    item: dict[str, Any] = {
        "rule": result.get("rule_id"),
        "marker": parts[1] if len(parts) > 1 else result.get("rule_id"),
        "status": result.get("status"),
        "summary": details.get("summary") or result.get("message"),
        "issues": issues[:EVIDENCE_CAP],
        "issues_total": max(
            len(issues),
            int(details.get("violation_count") or 0),
            int(details.get("divergence_count") or 0),
        ),
        "hints": list(result.get("fix_hints") or []),
    }
    if details.get("undecided"):
        item["undecided"] = list(details["undecided"])
    return item


def explain_result(result: dict[str, Any]) -> dict[str, Any]:
    """One result for a client: its rule key, status, message, hints, place
    and evidence (at most ``EVIDENCE_CAP``), its reason, and for a result
    that did not pass, its ``feedback``."""
    evidence = result.get("evidence") or []
    item: dict[str, Any] = {
        "rule": rule_key(result),
        "status": result["status"],
        "severity": result.get("severity"),
        "message": result.get("message"),
        "fix_hints": result.get("fix_hints") or [],
        "locations": result.get("locations"),
        "evidence": evidence[:EVIDENCE_CAP],
        "evidence_total": len(evidence),
    }
    reason = result_details(result).get("reason")
    if reason is not None:
        item["reason"] = reason
    if result["status"] != "OK":
        item["feedback"] = feedback(result)
    return item


__all__ = [
    "EVIDENCE_CAP",
    "explain_result",
    "feedback",
    "is_problem",
    "result_details",
    "rule_key",
]
