"""The verdict on one submission by a principle, from its report target.

A submission ``failed`` with any violation (a missing required entity is
one); else it is ``not_judged`` with any result without a verdict, or when
every result of the principle's checks was SKIPPED (a static run) or there is
none; else it ``passed``. Its violations are classified by the principle's
typical errors (``classify_target``); one no typical error explains counts as
``UNCLASSIFIED``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Optional

from pythonarchtesting.principles.catalog import Principle, PrincipleError
from pythonarchtesting.principles.classify import (
    BUILTIN_ERRORS,
    MISSING_REQUIRED_ENTITY,
    Finding,
    classify_target,
    principle_markers,
    rule_marker,
)
from pythonarchtesting.report.feedback import result_details

# The bucket of the violations no typical error of the principle explains.
UNCLASSIFIED = "unclassified"
# The verdicts of a submission by a principle.
PASSED, FAILED, NOT_JUDGED = "passed", "failed", "not_judged"
# The reason a submission is not judged when every result of the principle's
# checks was SKIPPED without one of its own, or when it has none at all.
SKIPPED_REASON = "skipped"
NO_CHECKS_REASON = "no_principle_checks"


def target_findings(principle: Principle, target: dict[str, Any]) -> list[Finding]:
    """The classified violations of one target, in the order of its results
    (``classify_target``: one finding per missing entity; with a file that
    does not parse, its syntax errors and the violations found in the rest)."""
    return classify_target(principle, target["results"])


def catalogue_errors(principle: Principle) -> list[PrincipleError]:
    """The principle's typical errors, then the tool's own."""
    return [*principle.errors, *BUILTIN_ERRORS.values()]


@dataclass(frozen=True)
class Judgement:
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


def relevant_results(
    principle: Principle, target: dict[str, Any]
) -> list[dict[str, Any]]:
    """The results of the principle's markers."""
    markers = principle_markers(principle)
    return [r for r in target["results"] if rule_marker(str(r["rule_id"])) in markers]


def unjudged_reason(results: list[dict[str, Any]]) -> Optional[str]:
    """Why results of the principle's checks give no verdict: none at all, or
    all SKIPPED (the reason of the first, e.g. ``dynamic_checks_disabled``)."""
    if not results:
        return NO_CHECKS_REASON
    if all(r["status"] == "SKIPPED" for r in results):
        return str(result_details(results[0]).get("reason") or SKIPPED_REASON)
    return None


def judge_submission(principle: Principle, target: dict[str, Any]) -> Judgement:
    """The verdict on one report target by ``principle`` (module docstring)."""
    findings = target_findings(principle, target)
    errors = list(
        dict.fromkeys(f.error_id or UNCLASSIFIED for f in findings if not f.not_judged)
    )
    reasons = list(dict.fromkeys(str(f.reason) for f in findings if f.not_judged))
    if not errors and not reasons:
        reason = unjudged_reason(relevant_results(principle, target))
        if reason is not None:
            reasons = [reason]
    if errors:
        verdict = FAILED
    elif reasons:
        verdict = NOT_JUDGED
    else:
        verdict = PASSED
    return Judgement(verdict, errors, reasons, findings)


def judge_submissions(
    principle: Principle, targets: list[dict[str, Any]]
) -> list[Judgement]:
    """``judge_submission`` of each target, in order."""
    return [judge_submission(principle, target) for target in targets]


def verdict_counts(judgements: Sequence[Judgement]) -> dict[str, int]:
    """How many submissions passed, failed and were not judged."""
    counts = Counter(j.verdict for j in judgements)
    return {verdict: counts[verdict] for verdict in (PASSED, FAILED, NOT_JUDGED)}


def not_judged_names(
    targets: list[dict[str, Any]], judgements: Sequence[Judgement]
) -> dict[str, list[str]]:
    """Reason -> the not judged submissions with it, first seen first."""
    names: dict[str, list[str]] = {}
    for target, judgement in zip(targets, judgements):
        if judgement.verdict == NOT_JUDGED:
            for reason in judgement.not_judged:
                names.setdefault(reason, []).append(target["display_name"])
    return names


def bucket_order(principle: Principle) -> list[str]:
    """Catalogue errors in catalogue order, then a missing entity, then the
    violations no typical error explains (a syntax error is no violation)."""
    return [error.id for error in principle.errors] + [
        MISSING_REQUIRED_ENTITY,
        UNCLASSIFIED,
    ]


__all__ = [
    "FAILED",
    "NOT_JUDGED",
    "NO_CHECKS_REASON",
    "PASSED",
    "SKIPPED_REASON",
    "UNCLASSIFIED",
    "Judgement",
    "bucket_order",
    "catalogue_errors",
    "judge_submission",
    "judge_submissions",
    "not_judged_names",
    "relevant_results",
    "target_findings",
    "unjudged_reason",
    "verdict_counts",
]
