"""Verdicts of the DYN001 / DYN003 / DYN004 evaluators on observed probe outcomes.

The probe outcome is placed in the batch cache, so these tests judge recorded
calls and writes without starting a child interpreter.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from pythonarchtesting.dynamic.batch import cache_key
from pythonarchtesting.dynamic.runner import ProbeOutcome
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.execution.evaluators.messages import (
    _has_caveat,
    build_rule_result,
)
from pythonarchtesting.execution.evaluators.runtime_structure import (
    RuntimeCallsEvaluator,
    RuntimeInstancesEvaluator,
    RuntimeReferenceCallsEvaluator,
    RuntimeWritesEvaluator,
)
from pythonarchtesting.matching import MatchStatus
from pythonarchtesting.rules.compilation import compile_rules


def _rule_and_entity(marker: str) -> tuple[Any, Any]:
    source = textwrap.dedent(f"""
        from typing import Annotated
        from pythonarchtesting.rules import (
            enforce_reference_calls,
            forbid_foreign_writes,
            forbid_runtime_calls,
            forbid_runtime_instantiation,
            require_runtime_calls,
        )

        def handle(request, service):
            __archtest__: Annotated[None, {marker}]
        """)
    entities = extract_entities_from_source(
        source,
        Path("controller.py"),
        Path("."),
        None,
        role="source",
        include_nested_functions=False,
        root_label="source",
    )
    rules, evidence, _ = compile_rules(entities, Mock())
    assert evidence == []
    entity = next(e for e in entities if e.kind == "function")
    return rules[0], entity


def _call(module: str, callee: str = "f", line: int = 3) -> dict:
    return {"module": module, "callee": callee, "caller": "handle", "line": line}


def _evaluate(
    marker: str, outcome: ProbeOutcome | None, target_root: Path | None = Path(".")
):
    rule, entity = _rule_and_entity(marker)
    ctx = SimpleNamespace(target_root=target_root, dynamic_cache={}, sandbox=None)
    if outcome is not None:
        ctx.dynamic_cache[cache_key(rule, entity)] = outcome
    match = SimpleNamespace(status=MatchStatus.MATCHED, confidence=1.0)
    evaluator = {
        "runtime_writes": RuntimeWritesEvaluator,
        "runtime_instances": RuntimeInstancesEvaluator,
    }.get(rule.rule_type, RuntimeCallsEvaluator)()
    return evaluator.evaluate(rule, entity, entity, match, ctx)


def _cases(*cases: dict) -> ProbeOutcome:
    return ProbeOutcome(
        status="completed",
        cases=[
            {"index": index, "status": "passed", "failures": [], **case}
            for index, case in enumerate(cases)
        ],
    )


_FORBID = (
    'forbid_runtime_calls("repository", allow=["repository.cache"], cases=[{}, {}])'
)
_REQUIRE = 'require_runtime_calls("service", "audit", cases=[{}, {}])'


def test_forbid_fails_on_a_call_into_the_module_or_a_submodule() -> None:
    result = _evaluate(
        _FORBID,
        _cases(
            {"calls": [_call("service"), _call("repository", "Repo.get", 7)]},
            {"calls": [_call("repository.sql")]},
        ),
    )

    assert result.status == "FAILED"
    assert result.details["violations"] == [
        "case 0: handle calls repository:Repo.get (line 7)",
        "case 1: handle calls repository.sql:f (line 3)",
    ]
    assert "(+1 more)" in result.message


def test_forbid_exempts_the_allow_list_and_unrelated_prefixes() -> None:
    result = _evaluate(
        _FORBID,
        _cases(
            {"calls": [_call("repository.cache"), _call("repository.cache.lru")]},
            {"calls": [_call("repository_utils")]},
        ),
    )

    assert result.status == "OK"
    assert result.details["summary"] == "no call into repository in 2 case(s)"


def test_require_passes_when_every_case_calls_every_module() -> None:
    result = _evaluate(
        _REQUIRE,
        _cases(
            {"calls": [_call("service"), _call("audit.log")]},
            {"calls": [_call("audit"), _call("service.orders")]},
        ),
    )

    assert result.status == "OK"
    assert (
        result.details["summary"] == "every case called into audit, service (2 case(s))"
    )


def test_require_fails_per_case_and_module_and_names_the_raise() -> None:
    result = _evaluate(
        _REQUIRE,
        _cases(
            {"calls": [_call("service")]},
            {"calls": [], "raised": "KeyError: 'id'"},
        ),
    )

    assert result.status == "FAILED"
    assert result.details["violations"] == [
        "case 0: no direct call into audit",
        "case 1: no direct call into audit; the call raised KeyError: 'id'",
        "case 1: no direct call into service; the call raised KeyError: 'id'",
    ]


def _lines(run: list[int], missed: list[int]) -> dict:
    return {"lines": {"file": "controller.py", "run": run, "missed": missed}}


def test_a_pass_names_the_lines_no_case_ran() -> None:
    result = _evaluate(
        _FORBID,
        _cases(
            _lines([3, 4, 5, 9], [6, 7, 8, 10]), _lines([3, 6, 9], [4, 5, 7, 8, 10])
        ),
    )

    assert result.status == "OK"
    assert result.details["coverage"] == {
        "file": "controller.py",
        "lines_total": 8,
        "lines_run": 5,
        "unexercised_lines": [7, 8, 10],
    }
    assert result.details["summary"] == (
        "no call into repository in 2 case(s); no case ran lines 7-8, 10 of "
        "controller.py, so they were not checked"
    )
    # The caveat reaches the one-line message, not only the details.
    assert result.message == f"OK: {result.details['summary']}"


def test_a_pass_with_every_line_run_adds_no_note() -> None:
    result = _evaluate(_FORBID, _cases(_lines([3, 4], []), _lines([3], [4])))

    assert result.details["coverage"]["unexercised_lines"] == []
    assert result.details["summary"] == "no call into repository in 2 case(s)"
    assert result.message == "OK"


@pytest.mark.parametrize(
    ("details", "caveat"),
    [
        ({"summary": "s", "coverage": {"unexercised_lines": [4]}}, True),
        ({"summary": "s", "unchecked_stages": ["save"]}, True),
        ({"summary": "s", "absences": ["audit"]}, True),
        ({"summary": "s", "coverage": {"unexercised_lines": []}}, False),
        ({"summary": "s", "unchecked_stages": [], "absences": []}, False),
        ({"coverage": {"unexercised_lines": [4]}}, False),  # nothing to say
    ],
)
def test_an_ok_message_carries_the_summary_only_with_a_caveat(
    details: dict, caveat: bool
) -> None:
    rule, entity = _rule_and_entity(_FORBID)
    match = SimpleNamespace(status=MatchStatus.MATCHED, confidence=1.0)

    result = build_rule_result(rule, entity, entity, match, "OK", details, ())

    assert _has_caveat(details) is caveat
    assert result.message == ("OK: s" if caveat else "OK")


@pytest.mark.parametrize(
    ("details", "reasons"),
    [
        (
            {"summary": "s", "coverage": {"unexercised_lines": [4]}},
            ["unexercised_lines"],
        ),
        ({"summary": "s", "unchecked_stages": ["save"]}, ["unchecked_stages"]),
        ({"summary": "s", "absences": ["audit"]}, ["reference_calls_not_made"]),
        (
            {"summary": "s", "cases": [{"index": 0, "raised": "ValueError: x"}]},
            ["case_raised"],
        ),
        ({"summary": "s", "coverage": {"unexercised_lines": []}}, None),
    ],
)
def test_a_pass_that_left_something_unchecked_lists_why(
    details: dict, reasons: list | None
) -> None:
    rule, entity = _rule_and_entity(_FORBID)
    match = SimpleNamespace(status=MatchStatus.MATCHED, confidence=1.0)

    result = build_rule_result(rule, entity, entity, match, "OK", details, ())

    assert result.details.get("unverified") == reasons


def test_a_failure_is_never_marked_unverified() -> None:
    rule, entity = _rule_and_entity(_FORBID)
    match = SimpleNamespace(status=MatchStatus.MATCHED, confidence=1.0)
    details = {"summary": "s", "coverage": {"unexercised_lines": [4]}}

    result = build_rule_result(rule, entity, entity, match, "FAILED", details, ())

    assert "unverified" not in result.details


def test_a_pass_whose_case_raised_says_what_did_not_run() -> None:
    result = _evaluate(_FORBID, _cases({"raised": "KeyError: 'id'"}))

    assert result.status == "OK"
    assert result.details["summary"] == (
        "no call into repository in 2 case(s); case 0 raised KeyError: 'id', "
        "so the code after it was not checked"
    )
    assert result.message.startswith("OK: ")


def test_a_missing_call_names_the_lines_that_did_not_run() -> None:
    result = _evaluate(
        _REQUIRE,
        _cases(
            {"calls": [_call("service"), _call("audit")]},
            {"calls": [_call("service")], **_lines([3], [5, 6])},
        ),
    )

    assert result.details["violations"] == [
        "case 1: no direct call into audit; lines 5-6 did not run in this case",
    ]


def test_a_raise_alone_does_not_fail_a_forbid_rule() -> None:
    result = _evaluate(_FORBID, _cases({"calls": [], "raised": "ValueError: x"}, {}))

    assert result.status == "OK"


def test_foreign_writes_fail_with_the_writer_and_location() -> None:
    write = {
        "class": "Account",
        "attribute": "balance",
        "writer": "bank:transfer",
        "file": "bank.py",
        "line": 9,
    }
    result = _evaluate(
        "forbid_foreign_writes(cases=[{}, {}])",
        _cases({"writes": []}, {"writes": [write]}),
    )

    assert result.status == "FAILED"
    assert result.details["violations"] == [
        "case 1: bank:transfer sets Account.balance at bank.py:9"
    ]


def test_no_foreign_writes_passes() -> None:
    result = _evaluate("forbid_foreign_writes(cases=[{}])", _cases({"writes": []}))

    assert result.status == "OK"
    assert result.details["summary"] == "no foreign attribute writes in 1 case(s)"


def test_a_case_that_cannot_be_set_up_fails_the_rule() -> None:
    result = _evaluate(
        _FORBID,
        _cases(
            {"calls": []},
            {"status": "error", "failures": ["setup: cannot resolve 'Missing'"]},
        ),
    )

    assert result.status == "FAILED"
    assert result.details["reason"] == "case_setup_failed"
    assert "case 1 could not run: setup: cannot resolve 'Missing'" in result.message


@pytest.mark.parametrize("status", ["timeout", "import_error", "crashed"])
def test_a_probe_that_did_not_complete_fails_the_rule(status: str) -> None:
    result = _evaluate(
        _REQUIRE, ProbeOutcome(status=status, error="boom", stderr="tail")
    )

    assert result.status == "FAILED"
    assert result.details["reason"] == f"probe_{status}"
    assert result.details["stderr_tail"] == "tail"


def test_without_dynamic_the_rule_is_skipped() -> None:
    result = _evaluate(_REQUIRE, None, target_root=None)

    assert result.status == "SKIPPED"
    assert result.details["reason"] == "dynamic_checks_disabled"


def test_without_a_batch_the_rule_runs_its_own_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pythonarchtesting.dynamic import runner

    seen: dict[str, Any] = {}

    def fake_run_cases(**kwargs: Any) -> ProbeOutcome:
        seen.update(kwargs)
        return _cases({"writes": []})

    monkeypatch.setattr(runner, "run_cases", fake_run_cases)

    result = _evaluate("forbid_foreign_writes(cases=[{}])", None)

    assert result.status == "OK"
    assert result.details["batched"] is False
    assert seen["observe"] == {"writes": True}
    assert seen["qualname"] == "handle"


def _instance(module: str, origin: str, cls: str = "Repo", line: int = 4) -> dict:
    return {
        "class": cls,
        "module": module,
        "from": origin,
        "creator": f"{origin}:handle",
        "file": f"{origin}.py",
        "line": line,
    }


_INSTANTIATION = (
    'forbid_runtime_instantiation("repository", allow=["repository.fake"], '
    "cases=[{}, {}])"
)


def test_instantiation_counts_only_objects_the_target_module_creates() -> None:
    _, entity = _rule_and_entity(_INSTANTIATION)
    own = entity.module_path
    result = _evaluate(
        _INSTANTIATION,
        _cases(
            {
                "instances": [
                    _instance("repository", "service"),
                    _instance("repository.sql", own, "SqlRepo", 9),
                ]
            },
            {"instances": [_instance("domain", own, "Order")]},
        ),
    )

    assert result.status == "FAILED"
    assert result.details["violations"] == [
        f"case 0: {own}:handle creates repository.sql:SqlRepo at {own}.py:9"
    ]


def test_instantiation_exempts_the_allow_list() -> None:
    _, entity = _rule_and_entity(_INSTANTIATION)
    result = _evaluate(
        _INSTANTIATION,
        _cases(
            {"instances": [_instance("repository.fake", entity.module_path)]},
            {},
        ),
    )

    assert result.status == "OK"
    assert result.details["summary"] == (
        "no instance of repository created in 2 case(s)"
    )


def test_instantiation_without_dynamic_is_skipped() -> None:
    result = _evaluate(_INSTANTIATION, None, target_root=None)

    assert result.status == "SKIPPED"


def _edge(origin: str, module: str, callee: str = "f", line: int = 3) -> dict:
    return {**_call(module, callee, line), "from": origin}


def _reference(
    marker: str,
    reference: ProbeOutcome,
    target: ProbeOutcome | None,
    monkeypatch: pytest.MonkeyPatch,
    *,
    dynamic: bool = True,
) -> tuple[Any, list[dict[str, Any]]]:
    from pythonarchtesting.dynamic import runner

    rule, entity = _rule_and_entity(marker)
    runs: list[dict[str, Any]] = []

    def fake_run_cases(**kwargs: Any) -> ProbeOutcome:
        runs.append(kwargs)
        if kwargs["target_root"] == Path("reference"):
            return reference
        assert target is not None, "the target must not run"
        return target

    monkeypatch.setattr(runner, "run_cases", fake_run_cases)
    ctx = SimpleNamespace(
        source_root=Path("reference") if dynamic else None,
        target_root=Path("target") if dynamic else None,
        dynamic_cache={},
        sandbox=None,
    )
    match = SimpleNamespace(status=MatchStatus.MATCHED, confidence=1.0)
    result = RuntimeReferenceCallsEvaluator().evaluate(rule, entity, entity, match, ctx)
    return result, runs


_REFERENCE = "enforce_reference_calls(cases=[{}, {}])"
_REFERENCE_ALL = "enforce_reference_calls(cases=[{}, {}], require_all=True)"
_REFERENCE_RUN = _cases(
    {"calls": [_edge("controller", "service"), _edge("service", "repository")]},
    {"calls": [_edge("controller", "service")]},
)


def test_reference_calls_without_dynamic_are_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, runs = _reference(
        _REFERENCE, _REFERENCE_RUN, None, monkeypatch, dynamic=False
    )

    assert result.status == "SKIPPED"
    assert result.details["reason"] == "dynamic_checks_disabled"
    assert runs == []


def test_reference_calls_pass_on_a_subset_and_run_reference_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, runs = _reference(
        _REFERENCE,
        _REFERENCE_RUN,
        _cases({"calls": [_edge("controller", "service")]}, {"calls": []}),
        monkeypatch,
    )

    assert result.status == "OK"
    assert [run["target_root"] for run in runs] == [Path("reference"), Path("target")]
    assert all(run["observe"] == {"calls": "edges"} for run in runs)
    assert result.details["reference_edges"] == [
        ["controller -> service", "service -> repository"],
        ["controller -> service"],
    ]
    assert result.details["summary"] == (
        "2 case(s) used only the reference's module calls; 2 reference call(s) "
        "never happened (not required without require_all)"
    )
    assert result.details["divergences"] == []
    assert result.details["absences"] == [
        "case 0: the reference's service -> repository never happened",
        "case 1: the reference's controller -> service never happened",
    ]


def test_reference_calls_fail_on_an_edge_the_reference_never_made(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bypass = _edge("controller", "repository", "Repo.get", 8)
    result, _ = _reference(
        _REFERENCE,
        _REFERENCE_RUN,
        _cases(
            {"calls": [_edge("controller", "service")]},
            {"calls": [bypass, {**bypass, "line": 9}]},
        ),
        monkeypatch,
    )

    assert result.status == "FAILED"
    # An edge counts once per case, however often it is crossed.
    assert result.details["violations"] == [
        "case 1: controller -> repository is not in the reference "
        "(handle calls repository:Repo.get (line 8))"
    ]


def test_reference_calls_require_all_reports_a_missing_edge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _cases(
        {"calls": [_edge("controller", "service")], "raised": "KeyError: 'id'"},
        {"calls": [_edge("controller", "service")]},
    )
    lenient, _ = _reference(_REFERENCE, _REFERENCE_RUN, target, monkeypatch)
    strict, _ = _reference(_REFERENCE_ALL, _REFERENCE_RUN, target, monkeypatch)

    assert lenient.status == "OK"
    assert strict.status == "FAILED"
    assert strict.details["require_all"] is True
    assert strict.details["violations"] == [
        "case 0: the reference's service -> repository never happened; "
        "the call raised KeyError: 'id'"
    ]


@pytest.mark.parametrize(
    ("reference", "cause"),
    [
        (
            ProbeOutcome(status="import_error", error="boom", stderr="tail"),
            "import_error: boom",
        ),
        (
            _cases({"status": "error", "failures": ["setup: no Missing"]}),
            "case 0: setup: no Missing",
        ),
    ],
)
def test_a_reference_that_does_not_run_is_an_error(
    reference: ProbeOutcome, cause: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, runs = _reference(_REFERENCE, reference, None, monkeypatch)

    assert result.status == "ERROR"
    assert result.details["reason"] == "reference_failed"
    assert result.details["summary"] == f"the reference itself did not run: {cause}"
    assert len(runs) == 1


def test_reference_calls_fail_when_a_target_case_cannot_be_set_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _ = _reference(
        _REFERENCE,
        _REFERENCE_RUN,
        _cases({"calls": []}, {"status": "error", "failures": ["setup: no Store"]}),
        monkeypatch,
    )

    assert result.status == "FAILED"
    assert result.details["reason"] == "case_setup_failed"
    assert "case 1 could not run: setup: no Store" in result.message


def test_reference_calls_fail_when_the_target_probe_does_not_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _ = _reference(
        _REFERENCE,
        _REFERENCE_RUN,
        ProbeOutcome(status="timeout", error="slow", stderr="tail"),
        monkeypatch,
    )

    assert result.status == "FAILED"
    assert result.details["reason"] == "probe_timeout"
    assert result.details["stderr_tail"] == "tail"


# Structured facts (B1 F3): one fact per violation, in the same order.


def test_forbid_runtime_calls_facts_match_violations() -> None:
    direct = {
        **_call("repository", "Repo.get", 7),
        "from": "controller",
        "file": "controller.py",
    }
    detour = {
        "from": "helpers",
        "module": "repository",
        "callee": "Repo.save",
        "caller": "store",
        "line": 5,
        "file": "helpers.py",
        "origin": {"from": "controller", "caller": "handle", "line": 4},
        "via": [
            {"module": "service", "caller": "Service.run"},
            {"module": "helpers", "caller": "store"},
        ],
    }
    result = _evaluate(
        'forbid_runtime_calls("repository", transitive=True, cases=[{}])',
        _cases({"calls": [direct, detour]}),
    )

    assert result.status == "FAILED"
    assert len(result.details["facts"]) == len(result.details["violations"]) == 2
    assert result.details["facts"] == [
        {
            "kind": "call",
            "case": 0,
            "caller": "controller:handle",
            "callee": "repository:Repo.get",
            "file": "controller.py",
            "line": 7,
            "via": [],
            "origin_line": None,
        },
        {
            "kind": "call",
            "case": 0,
            "caller": "controller:handle",
            "callee": "repository:Repo.save",
            "file": "helpers.py",
            "line": 5,
            "via": ["service:Service.run", "helpers:store"],
            "origin_line": 4,
        },
    ]


def test_require_runtime_calls_missing_call_fact() -> None:
    result = _evaluate(
        _REQUIRE,
        _cases(
            {"calls": [_call("service")]},
            {"calls": [], "raised": "KeyError: 'id'"},
        ),
    )

    assert result.details["facts"] == [
        {
            "kind": "missing_call",
            "case": 0,
            "module": "audit",
            "reference_module": "audit",
            "raised": None,
        },
        {
            "kind": "missing_call",
            "case": 1,
            "module": "audit",
            "reference_module": "audit",
            "raised": "KeyError: 'id'",
        },
        {
            "kind": "missing_call",
            "case": 1,
            "module": "service",
            "reference_module": "service",
            "raised": "KeyError: 'id'",
        },
    ]
    assert len(result.details["facts"]) == len(result.details["violations"])


def test_a_missing_call_fact_names_the_targets_module() -> None:
    rule, entity = _rule_and_entity(_REQUIRE)
    # The target renamed the reference's module ``audit`` to ``logbook``.
    source = SimpleNamespace(
        canonical_id="source:audit:record", module_path="audit", qualname="record"
    )
    target = SimpleNamespace(
        canonical_id="target:logbook:record", module_path="logbook", qualname="record"
    )
    ctx = SimpleNamespace(
        target_root=Path("."),
        dynamic_cache={cache_key(rule, entity): _cases({"calls": [_call("service")]})},
        sandbox=None,
        source_by_id={source.canonical_id: source},
        target_by_id={target.canonical_id: target},
        matches={
            source.canonical_id: SimpleNamespace(
                status=MatchStatus.MATCHED, target_id=target.canonical_id
            )
        },
    )
    match = SimpleNamespace(status=MatchStatus.MATCHED, confidence=1.0)

    result = RuntimeCallsEvaluator().evaluate(rule, entity, entity, match, ctx)

    assert result.details["facts"] == [
        {
            "kind": "missing_call",
            "case": 0,
            "module": "logbook",
            "reference_module": "audit",
            "raised": None,
        }
    ]
    assert result.details["violations"][0].startswith(
        "case 0: no direct call into audit"
    )


def _write(change: str, attribute: str, line: int) -> dict:
    return {
        "class": "Inventory",
        "attribute": attribute,
        "writer": "shop:sell",
        "file": "shop.py",
        "line": line,
        "change": change,
    }


def test_foreign_writes_facts() -> None:
    result = _evaluate(
        "forbid_foreign_writes(cases=[{}])",
        _cases(
            {"writes": [_write("assigned", "_stock", 10), _write("mutated", "log", 11)]}
        ),
    )

    assert result.details["violations"] == [
        "case 0: shop:sell sets Inventory._stock at shop.py:10",
        "case 0: shop:sell changes what is held in Inventory.log at shop.py:11",
    ]
    assert result.details["facts"] == [
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
            "case": 0,
            "change": "mutated",
            "writer": "shop:sell",
            "class": "Inventory",
            "attribute": "log",
            "file": "shop.py",
            "line": 11,
        },
    ]


def test_facts_aligned_with_violations_across_cases() -> None:
    result = _evaluate(
        _FORBID,
        _cases(
            {
                "calls": [
                    _call("service"),
                    _call("repository", "Repo.get", 7),
                    _call("repository.cache"),
                    _call("repository", "Repo.put", 8),
                ]
            },
            {"calls": [_call("repository.sql")]},
        ),
    )

    violations, facts = result.details["violations"], result.details["facts"]
    assert len(violations) == len(facts) == 3
    assert "(+2 more)" in result.message
    for text, fact in zip(violations, facts):
        assert text.startswith(f"case {fact['case']}: ")
        assert f"{fact['callee']} (line {fact['line']})" in text


def test_a_passing_rule_has_no_facts() -> None:
    result = _evaluate(_FORBID, _cases({"calls": []}, {"calls": []}))

    assert result.status == "OK"
    assert "facts" not in result.details


@pytest.mark.parametrize(
    "source",
    [
        "from rich import print\n",
        "from rich import echo as print\n",
        "import print\n",
        "def print(*args):\n    return None\n",
        "class print:\n    pass\n",
        "print = len\n",
        "print: object = len\n",
        "def f():\n    global print\n    print = len\n",
    ],
)
def test_the_static_scan_does_not_take_a_rebound_print_for_the_builtin(
    source: str,
) -> None:
    import ast

    from pythonarchtesting.execution.evaluators.runtime_structure import (
        _rebound_names,
    )

    assert "print" in _rebound_names(ast.parse(source))
    assert "input" not in _rebound_names(ast.parse(source))


def test_the_static_scan_keeps_a_print_nothing_rebinds() -> None:
    import ast

    from pythonarchtesting.execution.evaluators.runtime_structure import (
        _rebound_names,
    )

    tree = ast.parse("import builtins\nx = print\nprint('x')\n")
    assert _rebound_names(tree) == {"x", "builtins"}


def test_a_write_to_an_object_a_global_holds_says_held_in() -> None:
    from pythonarchtesting.execution.evaluators.runtime_structure import (
        _describe_write,
    )

    write = {
        "writer": "actions:take",
        "change": "mutated",
        "class": "Thing",
        "attribute": "where",
        "file": "actions.py",
        "line": 7,
        "held_by": "world.SACK",
    }

    assert _describe_write(write) == (
        "actions:take changes what is held in Thing.where (held in world.SACK) "
        "at actions.py:7"
    )


def test_a_forked_probe_of_the_rule_alone_is_taken_and_is_no_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``batch.prefetch`` may have run the rule's own probe forked from the
    interpreter that served the target; the evaluator takes that outcome
    instead of starting the same probe, and it still is no batch."""
    from pythonarchtesting.dynamic import runner
    from pythonarchtesting.dynamic.batch import observation, solo_key

    def no_probe(**_: Any) -> ProbeOutcome:
        raise AssertionError("the forked outcome was not taken")

    monkeypatch.setattr(runner, "run_cases", no_probe)
    rule, entity = _rule_and_entity("forbid_foreign_writes(cases=[{}])")
    ctx = SimpleNamespace(target_root=Path("."), dynamic_cache={}, sandbox=None)
    key = solo_key(
        module_path=entity.module_path,
        qualname=entity.qualname,
        kind=entity.kind,
        cases=[{}],
        init=None,
        timeout_s=5.0,
        observe=observation(rule),
    )
    ctx.dynamic_cache[key] = _cases({"writes": []})
    match = SimpleNamespace(status=MatchStatus.MATCHED, confidence=1.0)

    result = RuntimeWritesEvaluator().evaluate(rule, entity, entity, match, ctx)

    assert result.status == "OK"
    assert result.details["batched"] is False
    assert ctx.dynamic_cache == {}  # taken, not left for another rule
