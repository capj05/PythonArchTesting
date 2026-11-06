from __future__ import annotations

import functools
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from pythonarchtesting.mcp_server.errors import ToolInputError, require_absolute
from pythonarchtesting.mcp_server.principles import resolve_principle
from pythonarchtesting.principles import (
    BUILTIN_ERRORS,
    MISSING_REQUIRED_ENTITY,
    Finding,
    Principle,
    PrincipleError,
    classify_target,
    mapping_name,
    principle_markers,
    result_entity,
    rule_marker,
)
from pythonarchtesting.report.schema_v2 import validate_report_schema_v2

_MAX_LIMIT = 200
_TOP_RULES = 20
_EVIDENCE_CAP = 5
_NOT_PROBLEMS = ("OK", "SKIPPED")
# The bucket of the violations no typical error of the principle explains.
UNCLASSIFIED = "unclassified"
# The verdicts of a submission by a principle.
PASSED, FAILED, NOT_JUDGED = "passed", "failed", "not_judged"
# The reason a submission is not judged when every result of the principle's
# checks was SKIPPED without one of its own, or when it has none at all.
SKIPPED_REASON = "skipped"
NO_CHECKS_REASON = "no_principle_checks"
# The most submission names one bucket of class_overview lists.
_NAMES_CAP = 50

_F = TypeVar("_F", bound=Callable[..., dict[str, Any]])


def _malformed_as_input_error(func: _F) -> _F:
    """Report a hand-edited report that passes the schema but breaks traversal."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return func(*args, **kwargs)
        except (KeyError, TypeError, AttributeError) as error:
            raise ToolInputError(f"malformed report: {error!r}") from error

    return wrapper  # type: ignore[return-value]


def load_report(report_path: str) -> dict[str, Any]:
    """Read and validate a schema-v2 JSON report."""
    path = require_absolute(report_path, "report_path")
    if not path.is_file():
        raise ToolInputError(f"report_path does not exist: {report_path}")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ToolInputError(f"report is not valid JSON: {error}") from error
    errors = validate_report_schema_v2(report)
    if errors:
        raise ToolInputError(f"report is not a schema v2 report: {errors[0]}")
    return report  # type: ignore[no-any-return]


def rule_key(result: dict[str, Any]) -> str:
    """Identify a result; one rule_id can sit on several entities."""
    qualname = result["locations"]["source"]["qualname"]
    return f"{result['rule_id']}@{qualname}"


def _page(offset: int, limit: int) -> tuple[int, int]:
    return max(offset, 0), min(max(limit, 1), _MAX_LIMIT)


def _is_problem(result: dict[str, Any]) -> bool:
    return result["status"] not in _NOT_PROBLEMS


def _problems(target: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in target["results"] if _is_problem(r)]


def _findings(principle: Principle, target: dict[str, Any]) -> list[Finding]:
    """The classified violations of one target, in the order of its results
    (``classify_target``: one finding per missing entity; with a file that
    does not parse, its syntax errors and the violations found in the rest)."""
    return classify_target(principle, target["results"])


def _errors(principle: Principle) -> list[PrincipleError]:
    """The principle's typical errors, then the tool's own."""
    return [*principle.errors, *BUILTIN_ERRORS.values()]


@dataclass(frozen=True)
class _Judgement:
    """One submission by a principle.

    ``errors``: the distinct error ids of its violations, first seen first
    (``UNCLASSIFIED`` for a violation no typical error explains);
    ``not_judged``: the distinct reasons of its results without a verdict.
    ``verdict``: ``failed`` with any violation (a missing required entity is
    one); else ``not_judged`` with any
    result without a verdict, or when every result of the principle's checks
    was SKIPPED (a static run) or there is none; else ``passed``."""

    verdict: str
    errors: list[str]
    not_judged: list[str]
    findings: list[Finding]

    def row(self) -> dict[str, Any]:
        row: dict[str, Any] = {"verdict": self.verdict, "errors": self.errors}
        if self.not_judged:
            row["not_judged"] = self.not_judged
        return row


def _relevant(principle: Principle, target: dict[str, Any]) -> list[dict[str, Any]]:
    """The results of the principle's markers."""
    markers = principle_markers(principle)
    return [r for r in target["results"] if rule_marker(str(r["rule_id"])) in markers]


def _unjudged_reason(results: list[dict[str, Any]]) -> Optional[str]:
    """Why results of the principle's checks give no verdict: none at all, or
    all SKIPPED (the reason of the first, e.g. ``dynamic_checks_disabled``)."""
    if not results:
        return NO_CHECKS_REASON
    if all(r["status"] == "SKIPPED" for r in results):
        return str(_details(results[0]).get("reason") or SKIPPED_REASON)
    return None


def _judge(principle: Principle, target: dict[str, Any]) -> _Judgement:
    findings = _findings(principle, target)
    errors = list(
        dict.fromkeys(f.error_id or UNCLASSIFIED for f in findings if not f.not_judged)
    )
    reasons = list(dict.fromkeys(str(f.reason) for f in findings if f.not_judged))
    if not errors and not reasons:
        reason = _unjudged_reason(_relevant(principle, target))
        if reason is not None:
            reasons = [reason]
    if errors:
        verdict = FAILED
    elif reasons:
        verdict = NOT_JUDGED
    else:
        verdict = PASSED
    return _Judgement(verdict, errors, reasons, findings)


def _judge_all(principle: Principle, targets: list[dict[str, Any]]) -> list[_Judgement]:
    return [_judge(principle, target) for target in targets]


def _verdict_counts(judgements: list[_Judgement]) -> dict[str, int]:
    counts = Counter(j.verdict for j in judgements)
    return {verdict: counts[verdict] for verdict in (PASSED, FAILED, NOT_JUDGED)}


def _not_judged_names(
    targets: list[dict[str, Any]], judgements: list[_Judgement]
) -> dict[str, list[str]]:
    """Reason -> the not judged submissions with it, first seen first."""
    names: dict[str, list[str]] = {}
    for target, judgement in zip(targets, judgements):
        if judgement.verdict == NOT_JUDGED:
            for reason in judgement.not_judged:
                names.setdefault(reason, []).append(target["display_name"])
    return names


def _bucket_order(principle: Principle) -> list[str]:
    """Catalogue errors in catalogue order, then a missing entity, then the
    violations no typical error explains (a syntax error is no violation)."""
    return [error.id for error in principle.errors] + [
        MISSING_REQUIRED_ENTITY,
        UNCLASSIFIED,
    ]


def _bucket(names: list[str]) -> dict[str, Any]:
    return {
        "count": len(names),
        "submissions": names[:_NAMES_CAP],
        "submissions_total": len(names),
    }


def summarize_payload(
    report: dict[str, Any],
    report_path: str,
    offset: int = 0,
    limit: int = 50,
    principle: Optional[Principle] = None,
) -> dict[str, Any]:
    """Summarize an already loaded report; with a principle, also count the
    targets per typical error and list each target's errors."""
    offset, limit = _page(offset, limit)
    targets = report["targets"]
    failing: Counter[str] = Counter()
    skipped = 0
    undecided = 0
    for target in targets:
        for result in target["results"]:
            if result["status"] == "SKIPPED":
                skipped += 1
            elif result["status"] == "OK" and _details(result).get("undecided"):
                undecided += 1
        for key in {rule_key(r) for r in _problems(target)}:
            failing[key] += 1
    run = report.get("run", {})
    summary: dict[str, Any] = {
        "report_path": report_path,
        "exit_code": report["exit_code"],
        "mode": run.get("mode"),
        "source_path": run.get("source_path"),
        "targets_total": len(targets),
        "targets_failed": sum(1 for t in targets if t["exit_code"] != 0),
        "skipped_total": skipped,
        "undecided_total": undecided,
        "offset": offset,
        "limit": limit,
        "targets_page_total": len(targets),
        "targets": [
            {
                "target_id": t["target_id"],
                "display_name": t["display_name"],
                "exit_code": t["exit_code"],
                "problems": len(_problems(t)),
            }
            for t in targets[offset : offset + limit]
        ],
        "rules": [
            {"rule": key, "failing_targets": count, "of": len(targets)}
            for key, count in sorted(failing.items(), key=lambda i: (-i[1], i[0]))[
                :_TOP_RULES
            ]
        ],
    }
    if principle is not None:
        judgements = _judge_all(principle, targets)
        counts = Counter(error_id for j in judgements for error_id in j.errors)
        summary["principle"] = principle.id
        summary.update(_verdict_counts(judgements))
        summary["by_error"] = {
            error_id: counts[error_id]
            for error_id in _bucket_order(principle)
            if counts[error_id]
        }
        summary["not_judged_by_reason"] = {
            reason: len(names)
            for reason, names in _not_judged_names(targets, judgements).items()
        }
        for row, judgement in zip(
            summary["targets"], judgements[offset : offset + limit]
        ):
            row.update(judgement.row())
    return summary


@_malformed_as_input_error
def summarize_report(
    report_path: str,
    offset: int = 0,
    limit: int = 50,
    principle: Optional[str] = None,
) -> dict[str, Any]:
    entry = resolve_principle(principle) if principle is not None else None
    return summarize_payload(
        load_report(report_path), report_path, offset, limit, entry
    )


def _details(result: dict[str, Any]) -> dict[str, Any]:
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


def feedback(result: dict[str, Any]) -> dict[str, Any]:
    """What a client needs to explain one result to a student.

    The rule, its summary and fix hints, and the issues one by one: the edge
    (or path, or cycle), where the target makes it, and for the reference
    model what the reference's module does instead. A client writes the
    explanation from this; the server never does.
    """
    details = _details(result)
    issues: list[dict[str, Any]] = []
    for divergence in details.get("divergences") or []:
        issue = dict(divergence)
        layer = str(divergence.get("layer"))
        if layer != "external":
            # A library the reference uses is allowed from any module, so a
            # per-module list would mislead; the other layers have one.
            origin = str(divergence.get("edge", "")).split(" -> ")[0]
            issue["reference_allows"] = _reference_allows(details, layer, origin)
        issues.append(issue)
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
    for cycle in details.get("cycles") or []:
        route = list(cycle.get("path") or [])
        issues.append(
            _step_issue(
                "cycle", " -> ".join(route), route, list(cycle.get("steps") or [])
            )
        )
    facts = list(details.get("facts") or [])
    texts = list(details.get("violations") or [])
    if not issues and facts and len(facts) == len(texts):
        # Runtime rules (B1 F3): each fact with the violation text it states.
        issues = [{**fact, "text": str(text)} for fact, text in zip(facts, texts)]
    if not issues:
        if not texts and (details.get("summary") or result.get("message")):
            texts = [details.get("summary") or result.get("message")]
        issues = [{"kind": "violation", "text": str(text)} for text in texts]
    parts = str(result.get("rule_id", "")).split("/")
    item: dict[str, Any] = {
        "rule": result.get("rule_id"),
        "marker": parts[1] if len(parts) > 1 else result.get("rule_id"),
        "status": result.get("status"),
        "summary": details.get("summary") or result.get("message"),
        "issues": issues[:_EVIDENCE_CAP],
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


def _explain_result(result: dict[str, Any]) -> dict[str, Any]:
    evidence = result.get("evidence") or []
    item: dict[str, Any] = {
        "rule": rule_key(result),
        "status": result["status"],
        "severity": result.get("severity"),
        "message": result.get("message"),
        "fix_hints": result.get("fix_hints") or [],
        "locations": result.get("locations"),
        "evidence": evidence[:_EVIDENCE_CAP],
        "evidence_total": len(evidence),
    }
    reason = _details(result).get("reason")
    if reason is not None:
        item["reason"] = reason
    if result["status"] != "OK":
        item["feedback"] = feedback(result)
    return item


def _find_target(report: dict[str, Any], target: str) -> dict[str, Any]:
    targets: list[dict[str, Any]] = report["targets"]
    found: dict[str, Any] | None = next(
        (t for t in targets if t["target_id"] == target),
        None,
    ) or next((t for t in targets if t["display_name"] == target), None)
    if found is None:
        known = ", ".join(t["target_id"] for t in targets[:10])
        raise ToolInputError(
            f"unknown target {target!r}: the report has {len(targets)} targets "
            f"({known})"
        )
    return found


_PROPOSE_CANDIDATES = 3


@_malformed_as_input_error
def propose_mapping(report_path: str, target: str) -> dict[str, Any]:
    """The reference entities one target left unpaired, with their candidates.

    The material for a mapping (assisted pairing): an LLM client proposes
    pairs from it, and run_evaluation(mapping=...) checks and applies them.
    """
    found = _find_target(load_report(report_path), target)
    unpaired = []
    by_name = []
    for match in found["matching"]["matches"]:
        codes = {reason.get("code") for reason in match.get("reasons") or []}
        if match["status"] == "matched":
            # Paired by name, not by the scores: worth a look, and a mapping
            # replaces it.
            fallback = codes & {"unique_name", "member_of_paired_class"}
            if fallback and match.get("target_entity_id"):
                by_name.append(
                    {
                        "reference": mapping_name(match["source_entity_id"])[0],
                        "target": mapping_name(match["target_entity_id"])[0],
                        "rule": sorted(fallback)[0],
                    }
                )
            continue
        reference, kind = mapping_name(match["source_entity_id"])
        candidates = [
            {
                "target": mapping_name(candidate["target_entity_id"])[0],
                "confidence": candidate.get("confidence"),
            }
            for candidate in (match.get("candidates") or [])[:_PROPOSE_CANDIDATES]
            if candidate.get("target_entity_id")
        ]
        unpaired.append(
            {
                "reference": reference,
                "kind": kind,
                "status": match["status"],
                "candidates": candidates,
            }
        )
    return {
        "target_id": found["target_id"],
        "unpaired": unpaired,
        "paired_by_name": by_name,
        "mapping_template": {"pairs": {}},
        "note": (
            "Pair a module to pair its entities with the same name "
            '("controller": "handler"); pairs of different kinds, functions '
            "that cannot be called like the reference's and entities already "
            "matched by the scores are refused. paired_by_name lists pairs made "
            "by name only (unique_name, member_of_paired_class): a mapping for "
            "one of them replaces it."
        ),
    }


@_malformed_as_input_error
def explain_target(
    report_path: str,
    target: str,
    include_passed: bool = False,
    offset: int = 0,
    limit: int = 20,
    principle: Optional[str] = None,
) -> dict[str, Any]:
    """List the problem results of one target, optionally with passed ones.

    With a principle, list its findings instead of the results: its
    violations classified by the principle's typical errors, and its results
    without a verdict (``not_judged``); the typical errors' title, why and fix
    once, in ``errors``; with ``include_passed``, the passed results of the
    principle's checks (``passed``)."""
    entry = resolve_principle(principle) if principle is not None else None
    report = load_report(report_path)
    offset, limit = _page(offset, limit)
    found = _find_target(report, target)
    if entry is not None:
        judgement = _judge(entry, found)
        findings = judgement.findings
        page = findings[offset : offset + limit]
        explained: dict[str, Any] = {
            "target_id": found["target_id"],
            "display_name": found["display_name"],
            "exit_code": found["exit_code"],
            "principle": entry.id,
            "verdict": judgement.verdict,
        }
        if judgement.not_judged:
            explained["not_judged"] = judgement.not_judged
        explained.update(
            {
                "offset": offset,
                "limit": limit,
                "findings_total": len(findings),
                "findings": [f.to_dict(brief=True) for f in page],
                "errors": {
                    error.id: {"title": error.title, "why": error.why, "fix": error.fix}
                    for error in _errors(entry)
                    if any(f.error_id == error.id for f in page)
                },
            }
        )
        if include_passed:
            explained["passed"] = [
                {"rule": r["rule_id"], "target": result_entity(r)}
                for r in _relevant(entry, found)
                if r["status"] == "OK"
            ]
        return explained
    wanted = [
        r
        for r in found["results"]
        if _is_problem(r) or (include_passed and r["status"] == "OK")
    ]
    return {
        "target_id": found["target_id"],
        "display_name": found["display_name"],
        "exit_code": found["exit_code"],
        "offset": offset,
        "limit": limit,
        "results_total": len(wanted),
        "results": [_explain_result(r) for r in wanted[offset : offset + limit]],
    }


@_malformed_as_input_error
def explain_rule(
    report_path: str, rule: str, offset: int = 0, limit: int = 50
) -> dict[str, Any]:
    """Show how one rule fared on every target that has it."""
    report = load_report(report_path)
    offset, limit = _page(offset, limit)
    rows: list[tuple[bool, dict[str, Any]]] = []
    counts: Counter[str] = Counter()
    keys: set[str] = set()
    for target in report["targets"]:
        for result in target["results"]:
            key = rule_key(result)
            keys.add(key)
            if rule not in (key, result["rule_id"]):
                continue
            counts[result["status"]] += 1
            rows.append(
                (
                    not _is_problem(result),
                    {
                        "target_id": target["target_id"],
                        "display_name": target["display_name"],
                        "status": result["status"],
                        "message": result.get("message"),
                        **(
                            {"feedback": feedback(result)}
                            if _is_problem(result)
                            else {}
                        ),
                    },
                )
            )
    if not rows:
        raise ToolInputError(f"unknown rule {rule!r}: the report has {len(keys)} rules")
    rows.sort(key=lambda row: row[0])  # stable: problems first
    return {
        "rule": rule,
        "counts": dict(counts),
        "offset": offset,
        "limit": limit,
        "targets_total": len(rows),
        "targets": [row for _, row in rows[offset : offset + limit]],
    }


@_malformed_as_input_error
def class_overview(
    report_path: str,
    principle: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """The class at a glance by the typical errors of a principle.

    How many submissions passed, failed (a violation, or a reference entity
    without a counterpart: ``missing_required_entity``) and were not judged
    (no violation, but a result without a verdict, a file that does not
    parse, or every check SKIPPED); the three add up to ``submissions``. Per
    error id (in catalogue order, then ``missing_required_entity``,
    ``UNCLASSIFIED`` last, only those that occur) the number of submissions
    with it and their names (at most ``_NAMES_CAP``); the same per reason of
    the not judged ones; and a page of submissions with their verdict, error
    ids and reasons. The counts cover the whole report, not the page.

    A missing entity the submission has under another name (a function
    renamed into another language) is paired by a mapping: ``propose_mapping``
    lists the candidates, and ``run_evaluation(mapping=...)`` reruns with the
    pairs. A package without ``__init__.py``, or one importing its own modules
    absolutely (``from inventory import X``), is evaluated as the package it
    means (``docs/mcp.md``, "Beginner layouts").

    Without ``principle``, the one the report records (a run whose source was
    a task, ``run.principle``)."""
    report = load_report(report_path)
    principle = principle or (report.get("run") or {}).get("principle")
    if principle is None:
        raise ToolInputError(
            "give principle: the report records none (its source was no task)"
        )
    entry = resolve_principle(str(principle))
    offset, limit = _page(offset, limit)
    targets = report["targets"]
    judgements = _judge_all(entry, targets)
    names: dict[str, list[str]] = {}
    for target, judgement in zip(targets, judgements):
        for error_id in judgement.errors:
            names.setdefault(error_id, []).append(target["display_name"])
    titles = {error.id: error.title for error in _errors(entry)}
    by_error: dict[str, dict[str, Any]] = {}
    for error_id in _bucket_order(entry):
        if error_id not in names:
            continue
        bucket = _bucket(names[error_id])
        if error_id in titles:
            bucket = {"count": bucket.pop("count"), "title": titles[error_id], **bucket}
        by_error[error_id] = bucket
    return {
        "report_path": report_path,
        "principle": entry.id,
        "submissions": len(targets),
        **_verdict_counts(judgements),
        "by_error": by_error,
        "not_judged_by_reason": {
            reason: _bucket(found)
            for reason, found in _not_judged_names(targets, judgements).items()
        },
        "offset": offset,
        "limit": limit,
        "submissions_page": [
            {"name": target["display_name"], **judgement.row()}
            for target, judgement in list(zip(targets, judgements))[
                offset : offset + limit
            ]
        ],
    }
