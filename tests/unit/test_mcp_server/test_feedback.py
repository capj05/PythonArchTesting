"""Structured feedback for one result (F4.6): what to show a student."""

from __future__ import annotations

from typing import Any

from pythonarchtesting.mcp_server.reports import feedback


def _result(
    rule_id: str, details: dict[str, Any], hints: list[str] | None = None
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "status": "FAILED",
        "message": "fallback message",
        "fix_hints": hints or ["Do the right thing."],
        "details": details,
    }


def test_architecture_feedback_names_the_edge_and_what_the_reference_does():
    result = _result(
        "DEP004/architecture_entry/v1",
        {
            "summary": "import controller -> repository is not in the reference",
            "divergences": [
                {
                    "kind": "divergent",
                    "layer": "imports",
                    "edge": "controller -> repository",
                    "file": "controller.py",
                    "module": "controller",
                    "line": 1,
                }
            ],
            "architecture": {
                "imports": {
                    "convergent": ["controller -> service", "service -> models"],
                    "absent": ["controller -> config"],
                    "divergent": ["controller -> repository"],
                }
            },
            "undecided": ["imports: app -> models"],
        },
    )

    item = feedback(result)

    assert item["marker"] == "architecture_entry"
    assert item["summary"].startswith("import controller -> repository")
    (issue,) = item["issues"]
    assert issue["edge"] == "controller -> repository"
    assert (issue["file"], issue["line"]) == ("controller.py", 1)
    assert issue["reference_allows"] == [
        "controller -> config",
        "controller -> service",
    ]
    assert item["undecided"] == ["imports: app -> models"]
    assert item["hints"] == ["Do the right thing."]


def test_layer_paths_become_issues_with_their_steps():
    result = _result(
        "DEP002/enforce_layers/v1",
        {
            "summary": "repository imports controller",
            "paths": [
                {
                    "kind": "upward",
                    "from_layer": "repository",
                    "to_layer": "controller",
                    "steps": [
                        {
                            "from": "repository",
                            "to": "controller",
                            "filepath": "repository.py",
                            "lineno": 3,
                        }
                    ],
                }
            ],
        },
    )

    (issue,) = feedback(result)["issues"]

    assert issue["kind"] == "upward"
    assert issue["edge"] == "repository -> controller"
    assert (issue["file"], issue["line"]) == ("repository.py", 3)
    assert issue["path"] == ["repository", "controller"]


def test_cycles_become_issues():
    result = _result(
        "DEP003/forbid_cycles/v1",
        {
            "cycles": [
                {
                    "modules": ["a", "b"],
                    "path": ["a", "b", "a"],
                    "steps": [
                        {"from": "a", "to": "b", "filepath": "a.py", "lineno": 1},
                        {"from": "b", "to": "a", "filepath": "b.py", "lineno": 2},
                    ],
                }
            ]
        },
    )

    (issue,) = feedback(result)["issues"]

    assert issue["kind"] == "cycle"
    assert issue["edge"] == "a -> b -> a"
    assert (issue["file"], issue["line"]) == ("a.py", 1)


def test_other_rules_fall_back_to_their_violations_or_summary():
    with_violations = _result(
        "DYN001/forbid_runtime_calls/v1", {"violations": ["x calls db"]}
    )
    bare = _result("PRO001/implements_protocol/v1", {"summary": "send is missing"})

    assert feedback(with_violations)["issues"] == [
        {"kind": "violation", "text": "x calls db"}
    ]
    assert feedback(bare)["issues"] == [
        {"kind": "violation", "text": "send is missing"}
    ]


def test_external_divergences_carry_no_reference_allows():
    result = _result(
        "DEP004/architecture_entry/v1",
        {
            "divergences": [
                {
                    "kind": "divergent",
                    "layer": "external",
                    "edge": "controller -> requests",
                    "file": "controller.py",
                    "module": "controller",
                    "line": 1,
                }
            ],
            "architecture": {
                "external": {"convergent": ["controller -> json"], "absent": []}
            },
        },
    )

    (issue,) = feedback(result)["issues"]

    assert "reference_allows" not in issue


def test_without_summary_or_violations_the_message_is_the_issue():
    result = _result("ENT001/syntax/v1", {})

    assert feedback(result)["issues"] == [
        {"kind": "violation", "text": "fallback message"}
    ]


def test_reference_allows_includes_edges_an_exception_allows():
    result = _result(
        "DEP004/architecture_entry/v1",
        {
            "divergences": [
                {
                    "kind": "divergent",
                    "layer": "imports",
                    "edge": "controller -> repository",
                    "file": "controller.py",
                    "module": "controller",
                    "line": 1,
                }
            ],
            "architecture": {
                "imports": {
                    "convergent": ["controller -> service"],
                    "allowed": ["controller -> config"],
                }
            },
        },
    )

    (issue,) = feedback(result)["issues"]

    assert issue["reference_allows"] == [
        "controller -> config",
        "controller -> service",
    ]


def test_issues_total_counts_every_violation_not_the_capped_list():
    result = _result(
        "DEP003/forbid_cycles/v1",
        {
            "cycles": [
                {
                    "path": ["a", "b", "a"],
                    "steps": [
                        {"from": "a", "to": "b", "filepath": "a.py", "lineno": 1}
                    ],
                }
            ],
            "violation_count": 40,
        },
    )

    assert feedback(result)["issues_total"] == 40


def test_feedback_uses_facts_for_runtime_rules():
    texts = [
        "case 0: shop:sell sets Inventory._stock at shop.py:10",
        "case 1: shop:sell changes what is held in Inventory.log at shop.py:11",
    ]
    facts = [
        {
            "kind": "write",
            "case": 0,
            "change": "assigned",
            "writer": "shop:sell",
            "class": "Inventory",
            "attribute": "_stock",
            "file": "shop.py",
            "line": 10,
        },
        {
            "kind": "write",
            "case": 1,
            "change": "mutated",
            "writer": "shop:sell",
            "class": "Inventory",
            "attribute": "log",
            "file": "shop.py",
            "line": 11,
        },
    ]
    result = _result(
        "DYN004/forbid_foreign_writes/v1",
        {"summary": texts[0] + " (+1 more)", "violations": texts, "facts": facts},
    )

    issues = feedback(result)["issues"]

    assert [issue["kind"] for issue in issues] == ["write", "write"]
    assert [issue["text"] for issue in issues] == texts
    assert issues[1]["attribute"] == "log"
    assert issues[1]["change"] == "mutated"
    assert feedback(result)["issues_total"] == 2


def test_feedback_falls_back_to_the_texts_when_facts_do_not_line_up():
    texts = ["case 0: a calls db:x (line 1)", "case 1: a calls db:y (line 2)"]
    facts = [{"kind": "call", "case": 0, "callee": "db:x", "line": 1}]
    result = _result(
        "DYN001/forbid_runtime_calls/v1",
        {"summary": texts[0], "violations": texts, "facts": facts},
    )

    assert feedback(result)["issues"] == [
        {"kind": "violation", "text": text} for text in texts
    ]
