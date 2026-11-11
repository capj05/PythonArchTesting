"""MCP tools that read a JSON report: a summary, one target, one rule, the
class by a principle, and the material for a mapping.

The verdict on a submission by a principle is ``principles.verdict``'s; the
explanation of one result is ``report.feedback``'s. These tools page, shape
and check what the client gives (``ToolInputError``).
"""

from __future__ import annotations

import functools
from collections import Counter
from typing import Any, Callable, Optional, TypeVar

from pythonarchtesting.invalid_input import InvalidInputError
from pythonarchtesting.mcp_server.errors import ToolInputError, require_absolute
from pythonarchtesting.mcp_server.principles import resolve_principle
from pythonarchtesting.principles import Principle, mapping_name, result_entity
from pythonarchtesting.principles.verdict import (
    bucket_order,
    catalogue_errors,
    judge_submission,
    judge_submissions,
    not_judged_names,
    relevant_results,
    verdict_counts,
)
from pythonarchtesting.report.feedback import (
    explain_result,
    feedback,
    is_problem,
    result_details,
    rule_key,
)
from pythonarchtesting.report.load import read_report

_MAX_LIMIT = 200
_TOP_RULES = 20
# The most submission names one bucket of class_overview lists.
_NAMES_CAP = 50

_F = TypeVar("_F", bound=Callable[..., dict[str, Any]])


def _malformed_as_input_error(func: _F) -> _F:
    """Report a hand-edited report that passes the schema but breaks traversal."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return func(*args, **kwargs)
        except ToolInputError:
            raise
        except (KeyError, TypeError, AttributeError, ValueError) as error:
            raise ToolInputError(f"malformed report: {error!r}") from error

    return wrapper  # type: ignore[return-value]


def load_report(report_path: str) -> dict[str, Any]:
    """Read and validate a schema-v2 JSON report."""
    path = require_absolute(report_path, "report_path")
    if not path.is_file():
        raise ToolInputError(f"report_path does not exist: {report_path}")
    try:
        return read_report(path)
    except InvalidInputError as error:
        raise ToolInputError(str(error)) from error


def _page(offset: int, limit: int) -> tuple[int, int]:
    return max(offset, 0), min(max(limit, 1), _MAX_LIMIT)


def _problems(target: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in target["results"] if is_problem(r)]


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
            elif result["status"] == "OK" and result_details(result).get("undecided"):
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
        judgements = judge_submissions(principle, targets)
        counts = Counter(error_id for j in judgements for error_id in j.errors)
        summary["principle"] = principle.id
        summary.update(verdict_counts(judgements))
        summary["by_error"] = {
            error_id: counts[error_id]
            for error_id in bucket_order(principle)
            if counts[error_id]
        }
        summary["not_judged_by_reason"] = {
            reason: len(names)
            for reason, names in not_judged_names(targets, judgements).items()
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
    report = load_report(report_path)
    entry = _given_principle(report, principle)
    return summarize_payload(report, report_path, offset, limit, entry)


def _recorded_principle(report: dict[str, Any], principle: Optional[str]) -> Any:
    """``principle``, or without it the one the report records (a run whose
    source was a task, ``run.principle``); a principle other than the
    recorded one is a tool input error, as ``run_evaluation`` refuses one
    other than the task's."""
    recorded = (report.get("run") or {}).get("principle")
    if principle is not None and recorded is not None and principle != recorded:
        raise ToolInputError(
            f"principle {principle!r} is not the principle the report records: "
            f"the report records the principle {recorded!r} (its run's task); "
            "leave principle out or give that one"
        )
    return principle or recorded


def _given_principle(report: dict[str, Any], principle: Optional[str]) -> Any:
    """The catalogue entry of ``principle`` when it is given (it must be the
    one the report records, if any), else ``None``."""
    if principle is None:
        return None
    return resolve_principle(str(_recorded_principle(report, principle)))


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
    report = load_report(report_path)
    entry = _given_principle(report, principle)
    offset, limit = _page(offset, limit)
    found = _find_target(report, target)
    if entry is not None:
        judgement = judge_submission(entry, found)
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
                    for error in catalogue_errors(entry)
                    if any(f.error_id == error.id for f in page)
                },
            }
        )
        if include_passed:
            explained["passed"] = [
                {"rule": r["rule_id"], "target": result_entity(r)}
                for r in relevant_results(entry, found)
                if r["status"] == "OK"
            ]
        return explained
    wanted = [
        r
        for r in found["results"]
        if is_problem(r) or (include_passed and r["status"] == "OK")
    ]
    return {
        "target_id": found["target_id"],
        "display_name": found["display_name"],
        "exit_code": found["exit_code"],
        "offset": offset,
        "limit": limit,
        "results_total": len(wanted),
        "results": [explain_result(r) for r in wanted[offset : offset + limit]],
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
                    not is_problem(result),
                    {
                        "target_id": target["target_id"],
                        "display_name": target["display_name"],
                        "status": result["status"],
                        "message": result.get("message"),
                        **(
                            {"feedback": feedback(result)} if is_problem(result) else {}
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
    principle = _recorded_principle(report, principle)
    if principle is None:
        raise ToolInputError(
            "give principle: the report records none (its source was no task)"
        )
    entry = resolve_principle(str(principle))
    offset, limit = _page(offset, limit)
    targets = report["targets"]
    judgements = judge_submissions(entry, targets)
    names: dict[str, list[str]] = {}
    for target, judgement in zip(targets, judgements):
        for error_id in judgement.errors:
            names.setdefault(error_id, []).append(target["display_name"])
    titles = {error.id: error.title for error in catalogue_errors(entry)}
    by_error: dict[str, dict[str, Any]] = {}
    for error_id in bucket_order(entry):
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
        **verdict_counts(judgements),
        "by_error": by_error,
        "not_judged_by_reason": {
            reason: _bucket(found)
            for reason, found in not_judged_names(targets, judgements).items()
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


__all__ = [
    "class_overview",
    "explain_rule",
    "explain_target",
    "feedback",
    "load_report",
    "propose_mapping",
    "rule_key",
    "summarize_payload",
    "summarize_report",
]
