from __future__ import annotations

import functools
import json
from collections import Counter
from typing import Any, Callable, TypeVar

from pythonarchtesting.mcp_server.errors import ToolInputError, require_absolute
from pythonarchtesting.report.schema_v2 import validate_report_schema_v2

_MAX_LIMIT = 200
_TOP_RULES = 20
_EVIDENCE_CAP = 5
_NOT_PROBLEMS = ("OK", "SKIPPED")

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


def summarize_payload(
    report: dict[str, Any], report_path: str, offset: int = 0, limit: int = 50
) -> dict[str, Any]:
    """Summarize an already loaded report."""
    offset, limit = _page(offset, limit)
    targets = report["targets"]
    failing: Counter[str] = Counter()
    skipped = 0
    for target in targets:
        for result in target["results"]:
            if result["status"] == "SKIPPED":
                skipped += 1
        for key in {rule_key(r) for r in _problems(target)}:
            failing[key] += 1
    run = report.get("run", {})
    return {
        "report_path": report_path,
        "exit_code": report["exit_code"],
        "mode": run.get("mode"),
        "source_path": run.get("source_path"),
        "targets_total": len(targets),
        "targets_failed": sum(1 for t in targets if t["exit_code"] != 0),
        "skipped_total": skipped,
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


@_malformed_as_input_error
def summarize_report(
    report_path: str, offset: int = 0, limit: int = 50
) -> dict[str, Any]:
    return summarize_payload(load_report(report_path), report_path, offset, limit)


def _details(result: dict[str, Any]) -> dict[str, Any]:
    details = result.get("details") or {}
    if not isinstance(details, dict):
        raise TypeError(f"details must be an object, not {type(details).__name__}")
    return details


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
    return item


@_malformed_as_input_error
def explain_target(
    report_path: str,
    target: str,
    include_passed: bool = False,
    offset: int = 0,
    limit: int = 20,
) -> dict[str, Any]:
    """List the problem results of one target, optionally with passed ones."""
    report = load_report(report_path)
    offset, limit = _page(offset, limit)
    targets = report["targets"]
    found = next(
        (t for t in targets if t["target_id"] == target),
        None,
    ) or next((t for t in targets if t["display_name"] == target), None)
    if found is None:
        known = ", ".join(t["target_id"] for t in targets[:10])
        raise ToolInputError(
            f"unknown target {target!r}: the report has {len(targets)} targets "
            f"({known})"
        )
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
