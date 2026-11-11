"""``summarize_outcomes``: the outcomes of several principles in one report
(design § 5.6)."""

from __future__ import annotations

from typing import Any, Optional

from pythonarchtesting.global_mode.model import PrincipleOutcome, Status
from pythonarchtesting.global_mode.summary import summarize_outcomes


def _write(error_id: str, line: int = 3, case: int = 0) -> dict[str, Any]:
    return {
        "error_id": error_id,
        "rule": "DYN003/forbid_foreign_writes/v1",
        "target": "actions:take",
        "facts": {
            "kind": "write",
            "file": "actions.py",
            "line": line,
            "attribute": "_crates",
            "class": "Cargo",
            "case": case,
            "cases": [case],
        },
    }


def _outcome(
    principle: str,
    status: Status = "violated",
    findings: tuple[dict[str, Any], ...] = (),
    mutation: Optional[dict[str, str]] = None,
) -> PrincipleOutcome:
    return PrincipleOutcome(
        principle=principle,
        status=status,
        roles={},
        findings=findings,
        unverified=(),
        coverage=None,
        mutation=mutation,
        sites=1,
        violations=1 if findings else 0,
    )


def test_same_write_in_two_principles_is_one_finding_with_both_principles() -> None:
    summary = summarize_outcomes(
        [
            _outcome("encapsulation", findings=(_write("bypass_method"),)),
            # Another case of the same write: the same defect.
            _outcome(
                "strategy",
                findings=(_write("other_error", case=1), _write("x", 9)),
            ),
        ]
    )

    assert [p["principle"] for p in summary["principles"]] == [
        "encapsulation",
        "strategy",
    ]
    # Each principle still lists its own finding.
    assert len(summary["principles"][1]["findings"]) == 2
    first, second = summary["findings"]
    assert first["error_id"] == "bypass_method"
    assert first["principles"] == ["encapsulation", "strategy"]
    assert (second["facts"]["line"], second["principles"]) == (9, ["strategy"])


def test_finding_without_a_place_is_not_deduplicated() -> None:
    placeless = {"error_id": "logic_in_main", "facts": {"kind": "missing_call"}}

    summary = summarize_outcomes(
        [
            _outcome("io_separation", findings=(placeless,)),
            _outcome("strategy", findings=(dict(placeless),)),
        ]
    )

    assert [f["principles"] for f in summary["findings"]] == [
        ["io_separation"],
        ["strategy"],
    ]


def _call(callee: str, line: int = 19) -> dict[str, Any]:
    return {
        "error_id": "e",
        "facts": {"kind": "call", "callee": callee, "file": "actions.py", "line": line},
    }


def test_two_calls_on_one_line_are_two_findings() -> None:
    summary = summarize_outcomes(
        [
            _outcome("io_separation", findings=(_call("builtins:print"),)),
            _outcome("strategy", findings=(_call("builtins:open"),)),
        ]
    )

    assert [f["facts"]["callee"] for f in summary["findings"]] == [
        "builtins:print",
        "builtins:open",
    ]


def test_findings_of_one_principle_are_never_merged() -> None:
    summary = summarize_outcomes(
        [
            _outcome(
                "io_separation",
                findings=(_call("builtins:print"), _call("builtins:print")),
            ),
            _outcome("strategy", findings=(_call("builtins:print"),)),
        ]
    )

    assert [f["principles"] for f in summary["findings"]] == [
        ["io_separation", "strategy"],
        ["io_separation"],
    ]


def test_counts_per_status() -> None:
    summary = summarize_outcomes(
        [
            _outcome("io_separation", "violated", (_write("print_instead_of_return"),)),
            _outcome("encapsulation", "violated", (_write("bypass_method", 5),)),
            _outcome("polymorphism", "ok"),
            _outcome("strategy", "not_applied"),
        ]
    )

    assert summary["counts"] == {
        "not_applied": 1,
        "ok": 1,
        "unverified": 0,
        "violated": 2,
    }
