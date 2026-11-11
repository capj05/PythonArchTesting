"""``decide_status``: the status of one principle from its findings, the
prepared self-task and the dropped entities (design § 5.5)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.global_mode.discovery.io_separation import (
    POSSIBLY_INPUT_IN_LOGIC,
)
from pythonarchtesting.global_mode.model import (
    BoundEntity,
    PrincipleOutcome,
    RoleDiscovery,
)
from pythonarchtesting.global_mode.outcome import (
    MISSING_CALL_IN_SOME_CASES,
    MISSING_CALL_ROLE_DEPENDENT,
    MISSING_CALL_ROLE_DISPUTED,
    SELF_CALLS_UNOBSERVED,
    cases_per_entity,
    decide_status,
    families_of_classes,
    judge_principle,
    relax_missing_calls,
    relax_role_dependent,
    relax_self_calls,
    split_findings,
    unexercised_lines,
)
from pythonarchtesting.global_mode.selftask import (
    SelfTask,
    _source_entities,
    write_self_task,
)
from pythonarchtesting.principles.catalog import get_principle
from pythonarchtesting.principles.classify import Finding

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "global_mode"


def _discovery(
    not_applied: Optional[str] = None, disputed: Optional[str] = None
) -> RoleDiscovery:
    return RoleDiscovery(
        principle="io_separation",
        roles={
            "logic": (BoundEntity("actions", "code", "game logic", disputed),),
            "io": (BoundEntity("ui.main", "code", "reads input()"),),
        },
        conflicts=(),
        not_applied=not_applied,
    )


def _finding(
    error_id: Optional[str] = "print_instead_of_return",
    target: str = "actions:status",
    line: int = 19,
    reason: Optional[str] = None,
    facts: Optional[dict[str, Any]] = None,
    rule: str = "DYN001/forbid_runtime_calls/v1",
) -> Finding:
    return Finding(
        error_id=error_id,
        title=None,
        why=None,
        fix=None,
        facts=(
            {"callee": "builtins:print", "file": "actions.py", "line": line}
            if facts is None
            else facts
        ),
        rule=rule,
        target=target,
        text="print called",
        reason=reason,
    )


def _check(
    entity: str, coverage: Optional[float] = 1.0, accepted: bool = True
) -> dict[str, Any]:
    return {
        "role": "logic",
        "entity": entity,
        "marker": "forbid_runtime_calls",
        "cases_ran": True,
        "coverage": coverage,
        "accepted": accepted,
        "reasons": [] if accepted else [f"coverage of {entity} is below 80%"],
    }


def _prepared(
    checks: Optional[list[dict[str, Any]]] = None,
    errors: Optional[list[dict[str, Any]]] = None,
    problems: Optional[list[str]] = None,
) -> dict[str, Any]:
    checks = [_check("actions.status"), _check("ui.main")] if checks is None else checks
    errors = (
        [
            {"error": "print_instead_of_return", "status": "killed"},
            {"error": "logic_in_main", "status": "not_applicable"},
        ]
        if errors is None
        else errors
    )
    return {
        "accepted": not problems,
        "problems": problems or [],
        "checks": checks,
        "errors": errors,
        "reference_passes": True,
        "truncated": False,
    }


def test_not_applied_wins() -> None:
    status, unverified = decide_status(
        _discovery(not_applied="no function prints or reads input"),
        [_finding()],
        None,
        [{"entity": "actions.go", "role": "logic", "reason": "no cases"}],
    )

    assert (status, unverified) == ("not_applied", [])


def test_finding_is_violated_without_mutation() -> None:
    status, unverified = decide_status(_discovery(), [_finding()], None, [])

    assert (status, unverified) == ("violated", [])


def test_low_coverage_is_unverified_not_ok() -> None:
    prepared = _prepared(
        checks=[_check("actions.status", 0.5, accepted=False), _check("ui.main")]
    )

    status, unverified = decide_status(_discovery(), [], prepared, [])

    assert status == "unverified"
    assert [(u["entity"], u["reason"]) for u in unverified] == [
        ("actions.status", "coverage")
    ]
    assert unverified[0]["coverage"] == 0.5


def test_coverage_below_threshold_is_unverified_even_if_accepted() -> None:
    prepared = _prepared(checks=[_check("actions.status", 0.5)])

    status, unverified = decide_status(_discovery(), [], prepared, [], min_coverage=0.8)

    assert status == "unverified"
    assert [u["reason"] for u in unverified] == ["coverage"]


def test_not_verifiable_by_mutation_is_unverified() -> None:
    # prepare_task accepts a task with this status; global mode does not
    # call the principle ok on it.
    prepared = _prepared(
        errors=[
            {"error": "print_instead_of_return", "status": "killed"},
            {"error": "file_io_in_logic", "status": "not_verifiable_by_mutation"},
        ]
    )

    status, unverified = decide_status(_discovery(), [], prepared, [])

    assert status == "unverified"
    assert unverified == [
        {"error": "file_io_in_logic", "reason": "mutation:not_verifiable_by_mutation"}
    ]


def test_survived_mutant_is_unverified() -> None:
    prepared = _prepared(errors=[{"error": "input_in_logic", "status": "survived"}])

    status, unverified = decide_status(_discovery(), [], prepared, [])

    assert status == "unverified"
    assert [u["reason"] for u in unverified] == ["mutation:survived"]


def test_dropped_entity_is_unverified() -> None:
    dropped = [{"entity": "actions.go", "role": "logic", "reason": "no cases"}]

    status, unverified = decide_status(_discovery(), [], _prepared(), dropped)

    assert status == "unverified"
    assert unverified == [
        {"entity": "actions.go", "role": "logic", "reason": "no cases"}
    ]


def test_all_killed_and_covered_is_ok() -> None:
    status, unverified = decide_status(_discovery(), [], _prepared(), [])

    assert (status, unverified) == ("ok", [])


def test_not_judged_finding_is_unverified() -> None:
    finding = _finding(error_id=None, reason="case_setup_failed")

    status, unverified = decide_status(_discovery(), [finding], _prepared(), [])

    assert status == "unverified"
    assert unverified == [{"entity": "actions.status", "reason": "case_setup_failed"}]


def test_no_mutation_run_is_never_ok() -> None:
    status, unverified = decide_status(_discovery(), [], None, [])

    assert status == "unverified"
    assert [u["reason"] for u in unverified] == ["mutation:not_run"]


def test_problem_of_the_task_is_unverified() -> None:
    prepared = {**_prepared(), "accepted": False, "problems": ["role 'io' is unbound"]}

    status, unverified = decide_status(_discovery(), [], prepared, [])

    assert status == "unverified"
    assert unverified == [{"reason": "task", "why": "role 'io' is unbound"}]


def test_finding_of_disputed_entity_is_flagged_but_still_violated() -> None:
    discovery = _discovery(disputed="status is a debug helper, not game logic")
    findings = [_finding(), _finding(target="ui:main", line=8)]

    status, _ = decide_status(discovery, findings, None, [])
    classified, unclassified = split_findings(discovery, findings)

    assert status == "violated"
    assert classified[0]["role_disputed"] == "status is a debug helper, not game logic"
    assert "role_disputed" not in classified[1]
    assert unclassified == []


def test_unclassified_finding_alone_is_never_violated() -> None:
    # forbid_foreign_writes reports every write to a foreign project object;
    # one no typical error explains is shown, but never makes it violated.
    write = _finding(error_id=None, target="actions:go")
    discovery = _discovery()

    status, unverified = decide_status(discovery, [write], _prepared(), [])
    classified, unclassified = split_findings(discovery, [write])

    assert (status, unverified) == ("ok", [])
    assert classified == []
    assert [u["target"] for u in unclassified] == ["actions:go"]


def test_unclassified_finding_failing_the_reference_is_unverified_naming_it() -> None:
    # The target is a copy of the reference: the check that found it fails
    # on the reference too, and no mutant of its errors can be verified.
    call = _finding(error_id=None, target="commands:notes")
    reason = "forbid_runtime_calls fails on the reference: notes calls io:open_code"
    prepared = _prepared(
        errors=[
            {
                "error": "print_instead_of_return",
                "detected_by": "forbid_runtime_calls",
                "status": "reference_fails",
            },
            {
                "error": "logic_in_main",
                "detected_by": "require_runtime_calls",
                "status": "not_applicable",
            },
        ],
        problems=[reason],
    )

    status, unverified = decide_status(_discovery(), [call], prepared, [])

    assert status == "unverified"
    assert unverified == [
        {
            "error": "print_instead_of_return",
            "reason": "mutation:reference_fails",
            "because": "unclassified findings",
            "entities": ["commands.notes"],
            "why": reason,
        }
    ]


def test_blamed_marker_with_all_errors_not_applicable_is_ok() -> None:
    # The "fails on the reference" line is explained by the unclassified
    # finding; with no error left to verify, the status follows the errors.
    call = _finding(error_id=None, target="commands:notes")
    prepared = _prepared(
        errors=[
            {
                "error": "print_instead_of_return",
                "detected_by": "forbid_runtime_calls",
                "status": "not_applicable",
            }
        ],
        problems=["forbid_runtime_calls fails on the reference: notes calls open"],
    )
    discovery = _discovery()

    status, unverified = decide_status(discovery, [call], prepared, [])
    _, unclassified = split_findings(discovery, [call])

    assert (status, unverified) == ("ok", [])
    assert [u["target"] for u in unclassified] == ["commands:notes"]


def test_blamed_marker_with_no_mutants_names_the_cause() -> None:
    call = _finding(error_id=None, target="commands:notes")
    reason = "forbid_runtime_calls fails on the reference: notes calls open"
    prepared = _prepared(
        errors=[
            {
                "error": "print_instead_of_return",
                "detected_by": "forbid_runtime_calls",
                "status": "no_mutants",
            }
        ],
        problems=[reason],
    )

    status, unverified = decide_status(_discovery(), [call], prepared, [])

    assert status == "unverified"
    assert unverified == [
        {
            "error": "print_instead_of_return",
            "reason": "mutation:no_mutants",
            "because": "unclassified findings",
            "entities": ["commands.notes"],
            "why": reason,
        }
    ]


def test_finding_on_disputed_owner_class_is_flagged() -> None:
    # An encapsulation finding is on the client that wrote; the owner whose
    # object it wrote is the disputed entity.
    discovery = RoleDiscovery(
        principle="encapsulation",
        roles={
            "owner": (
                BoundEntity("ship.Cargo", "code", "list _crates", "a helper record"),
            ),
            "client": (BoundEntity("actions.take", "code", "takes a crate"),),
        },
        conflicts=(),
        not_applied=None,
    )
    write = _finding(
        error_id="bypass_method",
        target="actions:take",
        facts={"kind": "write", "class": "Cargo", "attribute": "_crates"},
        rule="DYN003/forbid_foreign_writes/v1",
    )
    other = _finding(
        error_id="bypass_method",
        target="actions:take",
        facts={"kind": "write", "class": "State", "attribute": "room"},
        rule="DYN003/forbid_foreign_writes/v1",
    )

    status, _ = decide_status(discovery, [write, other], None, [])
    classified, _ = split_findings(discovery, [write, other])

    assert status == "violated"
    assert classified[0]["role_disputed"] == "a helper record"
    assert "role_disputed" not in classified[1]


def test_check_without_coverage_is_unverified() -> None:
    prepared = _prepared(checks=[_check("actions.status", None), _check("ui.main")])

    status, unverified = decide_status(_discovery(), [], prepared, [])

    assert status == "unverified"
    assert unverified == [{"entity": "actions.status", "reason": "coverage"}]


def test_not_applicable_check_needs_no_coverage() -> None:
    check = {
        "role": "logic",
        "entity": "actions",
        "marker": "forbid_runtime_instantiation",
        "status": "not_applicable",
        "why": "binds no class",
        "accepted": True,
    }
    prepared = _prepared(checks=[check, _check("ui.main")])

    assert decide_status(_discovery(), [], prepared, []) == ("ok", [])


def test_role_left_unbound_by_dropped_entities_is_unverified(tmp_path: Path) -> None:
    # Cases only for console.run: every function of commands is dropped, the
    # role logic is left unbound and the core refuses the task.
    sub = FIXTURES / "detective_b"
    task = write_self_task(
        sub,
        "io_separation",
        roles={"logic": ["commands"], "io": ["console.run"]},
        cases={"console.run": [{"args": [], "stdin": "notes\n"}]},
        out_dir=tmp_path / "task",
    )
    discovery = RoleDiscovery(
        principle="io_separation",
        roles={
            "logic": (BoundEntity("commands", "code", "game logic"),),
            "io": (BoundEntity("console.run", "code", "reads input()"),),
        },
        conflicts=(),
        not_applied=None,
    )

    outcome = judge_principle(sub, discovery, task, tmp_path / "work")

    assert outcome.status == "unverified"
    reasons = [(u.get("entity"), u["reason"]) for u in outcome.unverified]
    assert reasons[0] == (None, "task")
    # Worded for global mode: the teacher writes no [roles] there.
    why = outcome.unverified[0]["why"]
    assert why.startswith("no logic was found, or every logic found lacks cases")
    assert "[roles]" not in why
    assert reasons[1:] == [
        ("commands.notes", "no cases"),
        ("commands.search", "no cases"),
        ("commands.walk", "no cases"),
    ]
    assert outcome.mutation is None
    assert not (tmp_path / "work").exists()


def test_outcome_lists_unclassified_findings() -> None:
    outcome = PrincipleOutcome(
        principle="io_separation",
        status="ok",
        roles={},
        findings=(),
        unverified=(),
        coverage=1.0,
        mutation={},
        sites=2,
        violations=0,
        unclassified=({"error_id": None, "target": "actions:go"},),
    )

    assert outcome.to_dict()["unclassified"] == [
        {"error_id": None, "target": "actions:go"}
    ]


def test_not_applied_principle_runs_nothing(tmp_path: Path) -> None:
    task = SelfTask(tmp_path / "task", ())

    outcome = judge_principle(
        tmp_path / "missing",
        _discovery(not_applied="no function prints or reads input"),
        task,
        tmp_path / "work",
    )

    assert outcome.status == "not_applied"
    assert (outcome.sites, outcome.violations, outcome.mutation) == (0, 0, None)
    assert not (tmp_path / "work").exists()


def test_disputed_role_keeps_an_otherwise_ok_principle_unverified() -> None:
    discovery = _discovery(disputed="possibly a helper, not game logic")

    status, unverified = decide_status(discovery, [], _prepared(), [])

    assert status == "unverified"
    assert unverified == [
        {
            "entity": "actions",
            "role": "logic",
            "reason": "role_disputed",
            "why": "possibly a helper, not game logic",
        }
    ]


def test_disputed_role_does_not_change_violated() -> None:
    discovery = _discovery(disputed="possibly a helper")

    status, unverified = decide_status(discovery, [_finding()], None, [])

    assert status == "violated"
    assert not any(u["reason"] == "role_disputed" for u in unverified)


def _missing_call(
    target: str = "ui:main", module: str = "actions", cases: tuple[int, ...] = (1,)
) -> Finding:
    facts: dict[str, Any] = {"kind": "missing_call", "module": module, "raised": None}
    if len(cases) == 1:
        facts["case"] = cases[0]
    else:
        facts["cases"] = list(cases)
    return _finding(
        error_id="logic_in_main",
        target=target,
        facts=facts,
        rule="DYN001/require_runtime_calls/v1",
    )


def _role_dependent(entity: str, module: str) -> dict[str, Any]:
    return {
        "entity": entity,
        "reason": MISSING_CALL_ROLE_DEPENDENT,
        "error": "logic_in_main",
        "module": module,
    }


def test_missing_call_in_every_case_is_unverified_never_violated() -> None:
    # Whether ui.main should call actions depends wholly on discovery's
    # roles: in global mode a missing call is never proof.
    finding = _missing_call(cases=(0, 1))

    status, unverified = decide_status(
        _discovery(), [finding], None, [], case_counts={"ui.main": 2}
    )
    classified, _ = split_findings(_discovery(), relax_role_dependent([finding]))

    assert status == "unverified"
    assert unverified == [
        _role_dependent("ui.main", "actions"),
        {"reason": "mutation:not_run"},
    ]
    assert classified == []


def test_missing_call_in_some_cases_is_unverified_not_violated() -> None:
    # Case 1 quits at once and calls no logic; case 0 called actions. A
    # missing call is evidence only when every case shows it.
    finding = _missing_call(cases=(1,))

    status, unverified = decide_status(
        _discovery(), [finding], None, [], case_counts={"ui.main": 2}
    )
    classified, _ = split_findings(
        _discovery(), relax_missing_calls([finding], {"ui.main": 2})
    )

    assert status == "unverified"
    assert unverified == [
        {
            "entity": "ui.main",
            "reason": MISSING_CALL_IN_SOME_CASES,
            "error": "logic_in_main",
            "module": "actions",
            "cases": [1],
            "case_count": 2,
        },
        {"reason": "mutation:not_run"},
    ]
    assert classified == []


def test_missing_calls_of_one_module_are_counted_together() -> None:
    # Two findings of one entity and module (they differ in what was raised)
    # together cover every case: no case called the module.
    first = _missing_call(cases=(0,))
    second = _missing_call(cases=(1,))
    second = replace(second, facts={**second.facts, "raised": "EOFError"})

    status, unverified = decide_status(
        _discovery(), [first, second], None, [], case_counts={"ui.main": 2}
    )

    assert status == "unverified"
    assert unverified[0] == _role_dependent("ui.main", "actions")


def test_missing_call_without_a_case_count_is_role_dependent() -> None:
    status, unverified = decide_status(
        _discovery(), [_missing_call(cases=(1,))], None, []
    )

    assert status == "unverified"
    assert unverified[0] == _role_dependent("ui.main", "actions")


def test_missing_call_beside_a_typical_error_leaves_it_violated() -> None:
    status, unverified = decide_status(
        _discovery(), [_finding(), _missing_call(cases=(0,))], None, []
    )

    assert status == "violated"
    assert unverified == [_role_dependent("ui.main", "actions")]


def test_ai_dispute_with_discovery_text_never_changes_a_typical_error() -> None:
    # An AI dispute that copies discovery's own doubt word for word: the
    # finding of a typical error that is no missing call stays violated.
    discovery = RoleDiscovery(
        principle="io_separation",
        roles={
            "logic": (BoundEntity("actions", "code", "game logic"),),
            "io": (
                BoundEntity(
                    "ui.main", "code", "reads input()", POSSIBLY_INPUT_IN_LOGIC
                ),
            ),
        },
        conflicts=(),
        not_applied=None,
    )
    finding = _finding(
        error_id="input_in_logic",
        target="ui:main",
        facts={"callee": "builtins:input", "file": "ui.py", "line": 4, "kind": "call"},
    )

    status, _ = decide_status(discovery, [finding], None, [])
    classified, _ = split_findings(discovery, [finding])

    assert status == "violated"
    assert classified[0]["role_disputed"] == POSSIBLY_INPUT_IN_LOGIC


def _oo_discovery(io: str, logic: tuple[str, ...]) -> RoleDiscovery:
    return RoleDiscovery(
        principle="io_separation",
        roles={
            "io": (BoundEntity(io, "code", "calls input()"),),
            "logic": tuple(
                BoundEntity(m, "code", "method the io calls") for m in logic
            ),
        },
        conflicts=(),
        not_applied=None,
    )


def test_missing_call_of_io_method_with_logic_in_its_class_is_unverified() -> None:
    # Game.run reaches Game.execute by self.execute(...), which the run does
    # not record: the missing call into game is no evidence.
    discovery = _oo_discovery("game.Game.run", ("game.Game.execute",))
    finding = _missing_call(target="game:Game.run", module="game", cases=(0, 1))
    families = {"game.Game": frozenset({"game.Game"})}

    status, unverified = decide_status(
        discovery,
        [finding],
        None,
        [],
        case_counts={"game.Game.run": 2},
        class_families=families,
    )
    classified, _ = split_findings(
        discovery, relax_self_calls([finding], discovery, families)
    )

    assert status == "unverified"
    assert unverified == [
        {
            "entity": "game.Game.run",
            "reason": SELF_CALLS_UNOBSERVED,
            "error": "logic_in_main",
            "module": "game",
            "logic": ["game.Game.execute"],
        },
        {"reason": "mutation:not_run"},
    ]
    assert classified == []


def test_missing_call_of_io_method_with_logic_in_a_subclass_is_unverified() -> None:
    discovery = _oo_discovery("game.Base.run", ("game.Game.go",))
    finding = _missing_call(target="game:Base.run", module="game", cases=(0,))
    family = frozenset({"game.Base", "game.Game"})

    status, unverified = decide_status(
        discovery,
        [finding],
        None,
        [],
        case_counts={"game.Base.run": 1},
        class_families={"game.Base": family, "game.Game": family},
    )

    assert status == "unverified"
    assert unverified[0]["reason"] == SELF_CALLS_UNOBSERVED


def test_missing_call_of_io_method_without_logic_in_its_family_is_role_dependent() -> (
    None
):
    # The logic is a method of another class: the io would call it on an
    # object (obj.m), which the run records.
    discovery = _oo_discovery("game.Game.run", ("world.Room.enter",))
    finding = _missing_call(target="game:Game.run", module="world", cases=(0,))
    families = {
        "game.Game": frozenset({"game.Game"}),
        "world.Room": frozenset({"world.Room"}),
    }

    status, unverified = decide_status(
        discovery,
        [finding],
        None,
        [],
        case_counts={"game.Game.run": 1},
        class_families=families,
    )

    assert status == "unverified"
    assert unverified[0]["reason"] == MISSING_CALL_ROLE_DEPENDENT


def test_missing_call_of_io_function_is_role_dependent_beside_a_class() -> None:
    # ui.main is no method: "ui" is no class, whatever the logic.
    discovery = _oo_discovery("ui.main", ("ui.Game.go",))
    finding = _missing_call(target="ui:main", module="ui", cases=(0,))

    status, unverified = decide_status(
        discovery,
        [finding],
        None,
        [],
        case_counts={"ui.main": 1},
        class_families={"ui.Game": frozenset({"ui.Game"})},
    )

    assert status == "unverified"
    assert unverified[0]["reason"] == MISSING_CALL_ROLE_DEPENDENT


def test_missing_call_without_class_families_is_role_dependent() -> None:
    discovery = _oo_discovery("game.Game.run", ("game.Game.execute",))
    finding = _missing_call(target="game:Game.run", module="game", cases=(0,))

    status, unverified = decide_status(
        discovery, [finding], None, [], case_counts={"game.Game.run": 1}
    )

    assert status == "unverified"
    assert unverified[0]["reason"] == MISSING_CALL_ROLE_DEPENDENT


def test_class_families_follow_project_bases_and_subclasses() -> None:
    families = families_of_classes(_source_entities(FIXTURES / "tavern_f"))

    # A family holds bases and subclasses, not siblings.
    assert families["game.Item"] == {"game.Item", "game.Key", "game.Potion"}
    assert families["game.Key"] == {"game.Item", "game.Key"}
    assert families["game.Game"] == {"game.Game"}


def _disputed_io_discovery(why: str) -> RoleDiscovery:
    return RoleDiscovery(
        principle="io_separation",
        roles={
            "io": (
                BoundEntity("actions.take", "code", "calls input()", why),
                BoundEntity("main.main", "code", "calls input()"),
            ),
            "logic": (BoundEntity("actions.look", "code", "the io calls it"),),
        },
        conflicts=(),
        not_applied=None,
    )


def test_missing_call_of_io_disputed_by_discovery_is_unverified() -> None:
    # actions.take reads the keyboard alone among the actions: maybe an
    # action (input_in_logic), maybe an input helper. Neither calls logic.
    discovery = _disputed_io_discovery(POSSIBLY_INPUT_IN_LOGIC)
    finding = _missing_call(target="actions:take", module="actions", cases=(0, 1))

    status, unverified = decide_status(
        discovery, [finding], None, [], case_counts={"actions.take": 2}
    )

    assert status == "unverified"
    assert unverified == [
        {
            "entity": "actions.take",
            "reason": MISSING_CALL_ROLE_DISPUTED,
            "error": "logic_in_main",
            "module": "actions",
        },
        {"reason": "mutation:not_run"},
        {
            "entity": "actions.take",
            "role": "io",
            "reason": "role_disputed",
            "why": POSSIBLY_INPUT_IN_LOGIC,
        },
    ]


def test_missing_call_of_io_disputed_by_the_ai_is_role_dependent() -> None:
    discovery = _disputed_io_discovery("the AI thinks it is a helper")
    finding = _missing_call(target="actions:take", module="actions", cases=(0,))

    status, unverified = decide_status(
        discovery, [finding], None, [], case_counts={"actions.take": 1}
    )

    assert status == "unverified"
    assert unverified[0]["reason"] == MISSING_CALL_ROLE_DEPENDENT


def test_case_counts_and_unexercised_lines_come_from_the_run() -> None:
    target = {
        "results": [
            {
                "rule_id": "DYN001/require_runtime_calls/v1",
                "target": {"module": "ui", "qualname": "main"},
                "details": {
                    "case_count": 2,
                    "coverage": {"file": "ui.py", "unexercised_lines": [9]},
                },
            },
            {
                "rule_id": "DYN001/forbid_runtime_calls/v1",
                "target": {"module": "logic", "qualname": "score"},
                "details": {
                    "case_count": 1,
                    "coverage": {"file": "logic.py", "unexercised_lines": [9, 8]},
                },
            },
            {
                "rule_id": "DYN001/forbid_runtime_calls/v1",
                "target": {"module": "logic", "qualname": "total"},
                "details": {
                    "case_count": 1,
                    "coverage": {"file": "logic.py", "unexercised_lines": []},
                },
            },
        ]
    }

    assert cases_per_entity(target) == {"ui.main": 2}
    assert unexercised_lines(get_principle("io_separation"), target) == [
        {"entity": "logic.score", "file": "logic.py", "lines": [8, 9]},
        {"entity": "ui.main", "file": "ui.py", "lines": [9]},
    ]


def test_outcome_lists_unexercised_lines_last() -> None:
    outcome = PrincipleOutcome(
        principle="io_separation",
        status="ok",
        roles={},
        findings=(),
        unverified=(),
        coverage=0.9,
        mutation={},
        sites=2,
        violations=0,
        unexercised=({"entity": "logic.score", "file": "logic.py", "lines": [9]},),
    )

    data = outcome.to_dict()
    assert data["unexercised"] == [
        {"entity": "logic.score", "file": "logic.py", "lines": [9]}
    ]
    assert list(data)[-1] == "unexercised"


def test_package_import_does_not_load_the_mcp_layer() -> None:
    import subprocess
    import sys

    code = (
        "import sys\n"
        "from pythonarchtesting.global_mode import decide_status, judge_principle, "
        "split_by_base\n"
        "assert not [m for m in sys.modules if m.startswith('pythonarchtesting.mcp_server')]\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_submission_copy_keeps_symlinks_and_skips_hidden_and_caches(
    tmp_path: Path,
) -> None:
    from pythonarchtesting.global_mode.outcome import _copy

    submission = tmp_path / "game"
    submission.mkdir()
    (submission / "game.py").write_text("print('hi')\n", encoding="utf-8")
    (submission / ".git").mkdir()
    (submission / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")
    (submission / "__pycache__").mkdir()
    (submission / "__pycache__" / "game.pyc").write_bytes(b"\0")
    (submission / "loop").symlink_to(".", target_is_directory=True)

    copy = _copy(submission, tmp_path / "work")

    # A symlink loop is copied as a link, not followed without end.
    assert (copy / "game.py").is_file()
    assert (copy / "loop").is_symlink()
    assert not (copy / ".git").exists()
    assert not (copy / "__pycache__").exists()
