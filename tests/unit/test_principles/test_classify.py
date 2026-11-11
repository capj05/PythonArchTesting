from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import pytest

from pythonarchtesting.principles import get_principle, load_catalog
from pythonarchtesting.principles.classify import (
    BUILTIN_ERRORS,
    MISSING_REQUIRED_ENTITY,
    SYNTAX_ERROR,
    Finding,
    callee_short,
    classify_result,
    classify_target,
    fill_what,
    principle_markers,
    rule_marker,
)

_WRITES = "DYN003/forbid_foreign_writes/v1"
_CALLS = "DYN001/forbid_runtime_calls/v1"
_SYNTAX = "extraction/syntax_error"


def _write(attribute: str, change: str, line: int = 10, **extra: Any) -> dict:
    return {
        "kind": "write",
        "case": 0,
        "change": change,
        "writer": "shop:sell",
        "class": "Inventory",
        "attribute": attribute,
        "file": "shop.py",
        "line": line,
        **extra,
    }


def _result(
    rule_id: str,
    facts: Optional[list[dict]] = None,
    texts: Optional[list[str]] = None,
    status: str = "FAILED",
    message: str = "the rule failed",
    reason: str = "violation",
) -> dict[str, Any]:
    details: dict[str, Any] = {"reason": reason}
    if facts is not None:
        details["facts"] = facts
        details["violations"] = (
            texts
            if texts is not None
            else [f"violation {i}" for i in range(len(facts))]
        )
    return {
        "rule_id": rule_id,
        "status": status,
        "message": message,
        "details": details,
        "target": {"file": "shop.py", "line": 8, "module": "shop", "qualname": "sell"},
    }


def test_exact_match_gives_the_catalogue_error():
    principle = get_principle("encapsulation")
    result = _result(_WRITES, [_write("_stock", "mutated")], ["case 0: sell writes"])

    [finding] = classify_result(principle, result)

    assert isinstance(finding, Finding)
    assert finding.error_id == "bypass_method"
    error = next(e for e in principle.errors if e.id == "bypass_method")
    assert (finding.title, finding.why, finding.fix) == (
        error.title,
        error.why,
        error.fix,
    )
    assert finding.rule == _WRITES
    assert finding.target == "shop:sell"
    assert finding.text == "case 0: sell writes"
    assert finding.facts["attribute"] == "_stock"
    assert finding.what is not None and "`Inventory._stock`" in finding.what


def test_one_finding_per_fact_in_order():
    principle = get_principle("encapsulation")
    facts = [_write("_stock", "assigned", 10), _write("log", "mutated", 11)]
    result = _result(_WRITES, facts, ["first", "second"])

    findings = classify_result(principle, result)

    assert [f.error_id for f in findings] == ["replace_attribute", "mutate_container"]
    assert [f.text for f in findings] == ["first", "second"]
    assert [f.facts["line"] for f in findings] == [10, 11]


def test_a_fact_no_error_matches_is_unclassified():
    principle = get_principle("encapsulation")
    # A write that deletes an attribute: no catalogue error declares "deleted".
    result = _result(_WRITES, [_write("_stock", "deleted")], ["case 0: deletes"])

    [finding] = classify_result(principle, result)

    assert finding.error_id is None
    assert finding.title is None and finding.why is None and finding.fix is None
    assert finding.what is None
    assert finding.text == "case 0: deletes"
    assert finding.facts["change"] == "deleted"


def test_the_error_of_another_marker_does_not_match():
    principle = get_principle("io_separation")
    call = {"kind": "call", "callee": "builtins:print", "caller": "a:b", "line": 3}
    result = _result("DYN002/require_runtime_calls/v1", [call])

    [finding] = classify_result(principle, result)

    assert finding.error_id is None


def test_most_specific_signature_wins(tmp_path: Path):
    package = Path(__file__).resolve().parents[3] / "src" / "pythonarchtesting"
    source = (package / "principles" / "catalog" / "io_separation.toml").read_text(
        encoding="utf-8"
    )
    # A broader error of the same marker, listed first: any print call.
    broad = (
        "[[errors]]\n"
        'id = "any_print"\n'
        'title = "printing"\n'
        'detected_by = "forbid_runtime_calls"\n'
        'what = "Function `{function}` prints."\n'
        'why = "Printing."\n'
        'fix = "Return instead."\n'
        'signature = { kind = "call", callee = "builtins:print" }\n'
    )
    head, sep, tail = source.partition("\n[[errors]]\n")
    (tmp_path / "io_separation.toml").write_text(
        head + "\n" + broad + sep + tail, encoding="utf-8"
    )
    principle = load_catalog(tmp_path)["io_separation"]
    assert principle.errors[0].id == "any_print"
    call = {"kind": "call", "callee": "builtins:print", "caller": "a:b", "line": 3}

    [finding] = classify_result(principle, _result(_CALLS, [call]))

    assert finding.error_id == "print_instead_of_return"
    other = {**call, "via": ["a:helper"]}
    [finding] = classify_result(principle, _result(_CALLS, [other]))
    assert finding.error_id == "output_through_helper"


def _unmatched(rule_id: str = _WRITES) -> dict[str, Any]:
    """A result as the report gives it for a reference entity the matching
    paired with nothing: the target dict exists, with every field ``None``."""
    result = _result(
        rule_id,
        status="FAILED",
        message="Required target entity missing or not matchable.",
        reason="required_target_missing",
    )
    result["target"] = {"file": None, "line": None, "module": None, "qualname": None}
    result["locations"] = {
        "source": {"module": "shop", "qualname": "sell", "file": "shop.py"},
        "target": {"module": None, "qualname": None, "file": None},
    }
    return result


def test_an_unmatched_entity_is_a_missing_required_entity():
    principle = get_principle("encapsulation")
    result = _unmatched()
    result["source_entity_id"] = (
        "source:source:shop:sell:function:p0-a3-v0-k0-w0-d0-kd0"
    )
    result["locations"]["source"]["line"] = 18

    [finding] = classify_result(principle, result)

    assert not finding.not_judged
    assert finding.error_id == MISSING_REQUIRED_ENTITY
    assert finding.title == BUILTIN_ERRORS[MISSING_REQUIRED_ENTITY].title
    assert finding.why and finding.fix
    assert finding.text == "Required target entity missing or not matchable."
    assert finding.facts == {
        "entity": "shop.sell",
        "kind": "function",
        "file": "shop.py",
        "line": 18,
        "rules": [_WRITES],
    }
    assert finding.target == "shop:sell"
    assert finding.what is not None and "`shop.sell`" in finding.what
    assert "shop.py:18" in finding.what


_READS = "ENC001/forbid_private_access/v1"


def _read(attribute: str, line: int, receiver: bool = False) -> dict:
    return {
        "kind": "read",
        "attribute": attribute,
        "class": "Inventory",
        "file": "shop.py",
        "line": line,
        "reader": "shop:sell",
        **({"receiver": True} if receiver else {}),
    }


def test_classify_target_drops_a_read_that_is_part_of_a_write():
    """``inventory._stock.setdefault(k, 0)`` reads ``_stock`` to change it:
    one defect, the write. A read of it on another line stays a finding."""
    principle = get_principle("encapsulation")
    writes = _result(_WRITES, [_write("_stock", "mutated", 10)])
    reads = _result(_READS, [_read("_stock", 10, True), _read("_stock", 12)])

    findings = classify_target(principle, [writes, reads])

    assert [(f.error_id, f.facts["line"]) for f in findings] == [
        ("bypass_method", 10),
        ("read_private", 12),
    ]
    # Without the write both reads are findings, in either order of results.
    assert len(classify_target(principle, [reads])) == 2
    assert [f.error_id for f in classify_target(principle, [reads, writes])] == [
        "read_private",
        "bypass_method",
    ]


def test_classify_target_keeps_a_read_on_a_write_line_that_is_no_receiver():
    """``inv._stock.update(other._stock)``, ``a._x = b._x`` and
    ``x = inv._log; inv._log = []``: the read of the other object (or the
    read before the write) is a defect of its own; only the receiver of the
    method call that makes the write goes."""
    principle = get_principle("encapsulation")
    writes = _result(_WRITES, [_write("_stock", "mutated", 10)])
    reads = _result(_READS, [_read("_stock", 10, True), _read("_stock", 10)])

    findings = classify_target(principle, [writes, reads])

    assert [(f.error_id, f.facts["line"]) for f in findings] == [
        ("bypass_method", 10),
        ("read_private", 10),
    ]
    assert "receiver" not in findings[1].facts


def _isinstance(case: int, line: int, caller: str = "report:total") -> dict:
    return {
        "kind": "call",
        "case": case,
        "callee": "builtins:isinstance",
        "caller": caller,
        "file": "report.py",
        "line": line,
        "via": [],
    }


def test_classify_target_gives_one_finding_per_defect_not_per_case():
    """The same call site in every case, and in a helper two client
    functions share, is one ``type_switch``; another line is another."""
    principle = get_principle("polymorphism")
    total = _result(
        _CALLS, [_isinstance(0, 11), _isinstance(1, 11), _isinstance(0, 13)]
    )
    describe = _result(_CALLS, [_isinstance(0, 11, "report:_kind")])

    findings = classify_target(principle, [total, describe])

    assert [(f.error_id, f.facts["line"]) for f in findings] == [
        ("type_switch", 11),
        ("type_switch", 13),
    ]
    assert findings[0].facts["cases"] == [0, 1]
    assert "cases" not in findings[1].facts


def _warn(case: int, caller: str, origin_line: int) -> dict:
    """A print in a helper module, reached by ``caller`` through ``warn()``."""
    return {
        "kind": "call",
        "case": case,
        "callee": "builtins:print",
        "caller": caller,
        "file": "messages.py",
        "line": 5,
        "via": ["messages:warn"],
        "origin_line": origin_line,
    }


def test_classify_target_keeps_each_caller_of_a_shared_helper_apart():
    """Two logic functions that both call a printing helper are two defects,
    though the print is one line: each caller is fixed on its own line. The
    cases of one caller are not merged into the other's."""
    principle = get_principle("io_separation")
    parse = _result(_CALLS, [_warn(0, "grades:parse_grades", 6)])
    average = _result(
        _CALLS,
        [_warn(0, "grades:average", 20), _warn(1, "grades:average", 20)],
    )

    findings = classify_target(principle, [parse, average])

    assert [
        (f.error_id, f.facts["caller"], f.facts.get("cases")) for f in findings
    ] == [
        ("output_through_helper", "grades:parse_grades", None),
        ("output_through_helper", "grades:average", [0, 1]),
    ]


def test_classify_target_collapses_a_write_that_differs_only_in_its_case():
    principle = get_principle("encapsulation")
    writes = _result(
        _WRITES,
        [
            _write("_stock", "mutated", 10),
            {**_write("_stock", "mutated", 10), "case": 1},
            _write("_stock", "assigned", 10),
        ],
    )

    findings = classify_target(principle, [writes])

    assert [(f.error_id, f.facts.get("cases")) for f in findings] == [
        ("bypass_method", [0, 1]),
        ("replace_attribute", None),
    ]


def test_classify_target_gives_one_missing_entity_for_several_rules():
    principle = get_principle("encapsulation")
    first, second, other = _unmatched(), _unmatched(_CALLS), _unmatched()
    for result in (first, second):
        result["source_entity_id"] = "source:source:shop:sell:function:-"
    other["source_entity_id"] = "source:source:shop:restock:function:-"
    violation = _result(_WRITES, [_write("_stock", "mutated")])

    findings = classify_target(principle, [first, violation, second, other])

    assert [f.error_id for f in findings] == [
        MISSING_REQUIRED_ENTITY,
        "bypass_method",
        MISSING_REQUIRED_ENTITY,
    ]
    assert findings[0].facts["rules"] == [_WRITES, _CALLS]
    assert findings[2].facts["entity"] == "shop.restock"


def _syntax_error(file: Optional[str]) -> dict[str, Any]:
    """A file that does not parse: the submission's (``details.file``) or,
    without it, the reference's, which every target's results repeat."""
    result = _result(_SYNTAX, status="ERROR", message="Syntax error.", reason="")
    result["details"] = {
        "exception": "invalid syntax (shop.py, line 25)",
        "message": "invalid syntax",
        "lineno": 25,
        "offset": 12,
    }
    if file is not None:
        result["details"]["file"] = file
    result["target"] = {"file": None, "line": None, "module": None, "qualname": None}
    return result


def test_a_syntax_error_drops_only_what_follows_from_unreadable_code():
    """The entities without a counterpart and the checks that could not run
    may follow from the file the tool could not read: dropped. A violation
    found in the code it could read stays, classified or not."""
    principle = get_principle("encapsulation")
    results = [
        _unmatched(),
        _result(_WRITES, [_write("_stock", "mutated")]),
        _syntax_error("shop.py"),
        _result(_WRITES, reason="probe_import_error"),
        _result(_CALLS, [{"kind": "call", "callee": "os:system"}]),
    ]

    findings = classify_target(principle, results)

    assert [(f.error_id, f.reason) for f in findings] == [
        ("bypass_method", None),
        (SYNTAX_ERROR, SYNTAX_ERROR),
        (None, None),
    ]


def test_a_syntax_error_alone_is_the_only_finding():
    principle = get_principle("encapsulation")
    results = [
        _unmatched(),
        _syntax_error("shop.py"),
        _result(_WRITES, reason="probe_import_error"),
    ]

    [finding] = classify_target(principle, results)

    assert finding.error_id == SYNTAX_ERROR
    assert finding.not_judged and finding.reason == SYNTAX_ERROR
    assert finding.facts == {
        "file": "shop.py",
        "line": 25,
        "offset": 12,
        "message": "invalid syntax",
    }
    assert finding.what == "File `shop.py` does not parse: invalid syntax (line 25)."
    data = finding.to_dict(brief=True)
    assert (data["error_id"], data["not_judged"], data["reason"]) == (
        SYNTAX_ERROR,
        True,
        SYNTAX_ERROR,
    )


@pytest.mark.parametrize(
    ("status", "reason"),
    [("low_confidence", "low_confidence_match"), ("ambiguous", "ambiguous_match")],
)
def test_an_uncertain_match_is_not_judged_not_missing(status: str, reason: str):
    """The submission may have the entity: the tool only could not pair it
    with certainty, so it names the best candidate and judges nothing."""
    principle = get_principle("encapsulation")
    first, second = _unmatched(), _unmatched(_CALLS)
    for result in (first, second):
        result["source_entity_id"] = "source:source:shop:sell:function:-"
        result["target_entity_id"] = "target:capj05_capsky:shop:prodej:function:-"
        result["details"]["match_status"] = status
        result["details"]["confidence"] = 0.68

    [finding] = classify_target(principle, [first, second])

    assert finding.error_id is None
    assert finding.not_judged and finding.reason == reason
    assert finding.facts == {
        "entity": "shop.sell",
        "kind": "function",
        "file": "shop.py",
        "match_status": status,
        "confidence": 0.68,
        "candidate": "shop.prodej",
        "rules": [_WRITES, _CALLS],
    }
    assert finding.target == "shop:sell"
    assert finding.what is not None and "`shop.prodej`" in finding.what


def _setup_failed(target: str, unresolved: Optional[str]) -> dict[str, Any]:
    """A case that could not run: the probe names the case's reference
    (``$new``) it could not resolve in the submission, if that was why."""
    module, qualname = target.split(":")
    result = _result(_WRITES, reason="case_setup_failed", message=f"{target}: setup")
    result["target"] = {
        "file": "shop.py",
        "line": 8,
        "module": module,
        "qualname": qualname,
    }
    case: dict[str, Any] = {
        "index": 0,
        "status": "error",
        "failures": [f"setup: cannot resolve {unresolved!r}: no attribute 'X'"],
    }
    if unresolved is not None:
        case["unresolved"] = unresolved
    result["details"]["cases"] = [{"index": 1, "status": "passed"}, case]
    return result


def test_an_unresolvable_case_reference_is_one_missing_required_entity():
    principle = get_principle("encapsulation")
    results = [
        _setup_failed("shop:sell", "inventory.Inventory"),
        _setup_failed("shop:restock", "inventory.Inventory"),
        _setup_failed("shop:report", None),
    ]

    findings = classify_target(principle, results)

    assert [(f.error_id, f.reason) for f in findings] == [
        (MISSING_REQUIRED_ENTITY, None),
        (None, "case_setup_failed"),
    ]
    missing = findings[0]
    assert missing.facts == {
        "entity": "inventory.Inventory",
        "rules": [_WRITES],
        "required_by": ["shop:sell", "shop:restock"],
    }
    assert missing.target == "inventory:Inventory"
    assert missing.what is not None and "`inventory.Inventory`" in missing.what


def test_a_syntax_error_of_the_reference_is_no_syntax_error_finding():
    principle = get_principle("encapsulation")

    [finding] = classify_target(principle, [_syntax_error(None)])

    assert finding.error_id is None
    assert finding.not_judged and finding.reason == "error"


def test_the_entity_falls_back_to_the_result_source():
    principle = get_principle("encapsulation")
    result = _unmatched()
    del result["locations"]
    result["source"] = {"module": "shop", "qualname": "restock"}

    [finding] = classify_result(principle, result)

    assert finding.target == "shop:restock"


@pytest.mark.parametrize(
    ("status", "reason", "expected"),
    [
        ("FAILED", "probe_import_error", "probe_import_error"),
        ("FAILED", "case_setup_failed", "case_setup_failed"),
        ("FAILED", "", "no_facts"),
        ("ERROR", "reference_failed", "reference_failed"),
        ("ERROR", "", "error"),
    ],
)
def test_a_failure_without_facts_is_not_judged(status: str, reason: str, expected: str):
    principle = get_principle("encapsulation")
    result = _result(_WRITES, status=status, message="import_error", reason=reason)

    [finding] = classify_result(principle, result)

    assert finding.not_judged and finding.reason == expected
    assert finding.target == "shop:sell"
    assert finding.text == "import_error"


def test_an_error_with_facts_is_still_not_judged():
    principle = get_principle("encapsulation")
    result = _result(_WRITES, [_write("_stock", "mutated")], status="ERROR", reason="")

    [finding] = classify_result(principle, result)

    assert finding.not_judged and finding.reason == "error"


def test_a_violation_is_judged():
    principle = get_principle("encapsulation")
    classified, unclassified = classify_result(
        principle,
        _result(_WRITES, [_write("_stock", "mutated"), _write("_stock", "deleted")]),
    )

    assert not classified.not_judged and classified.reason is None
    assert not unclassified.not_judged and unclassified.error_id is None


def test_passed_skipped_and_warning_results_have_no_findings():
    principle = get_principle("encapsulation")
    for status in ("OK", "SKIPPED", "WARNING"):
        assert classify_result(principle, _result(_WRITES, [], status=status)) == []


def test_facts_that_do_not_line_up_with_the_texts_use_the_message():
    principle = get_principle("encapsulation")
    result = _result(_WRITES, [_write("_stock", "mutated")], texts=[])

    [finding] = classify_result(principle, result)

    assert finding.text == "the rule failed"


def test_to_dict_is_compact_json_and_keeps_a_null_error_id():
    principle = get_principle("encapsulation")
    classified = classify_result(
        principle, _result(_WRITES, [_write("log", "mutated")])
    )
    unclassified = classify_result(
        principle, _result(_WRITES, [_write("_stock", "deleted")])
    )

    data = classified[0].to_dict()
    assert json.loads(json.dumps(data)) == data
    assert data["error_id"] == "mutate_container"
    empty = unclassified[0].to_dict()
    assert empty["error_id"] is None
    assert "why" not in empty and "title" not in empty
    assert "not_judged" not in data and "not_judged" not in empty
    not_run = _result(_WRITES, message="import_error", reason="probe_import_error")
    lost = classify_result(principle, not_run)[0].to_dict()
    assert lost["error_id"] is None
    assert (lost["not_judged"], lost["reason"]) == (True, "probe_import_error")
    assert lost["target"] == "shop:sell"
    brief = classified[0].to_dict(brief=True)
    assert {"title", "why", "fix", "text"}.isdisjoint(brief)
    assert classify_result(principle, not_run)[0].to_dict(brief=True)["text"]
    assert brief["what"] == data["what"]


@pytest.mark.parametrize(
    ("rule_id", "marker"),
    [
        ("DYN003/forbid_foreign_writes/v1", "forbid_foreign_writes"),
        ("forbid_foreign_writes", "forbid_foreign_writes"),
    ],
)
def test_rule_marker(rule_id: str, marker: str):
    assert rule_marker(rule_id) == marker


def test_principle_markers_cover_checks_and_errors():
    assert principle_markers(get_principle("encapsulation")) == {
        "forbid_foreign_writes",
        "forbid_private_access",
    }
    assert principle_markers(get_principle("io_separation")) == {
        "forbid_runtime_calls",
        "require_runtime_calls",
    }


@pytest.mark.parametrize(
    ("callee", "short"),
    [
        ("builtins:print", "print()"),
        ("builtins:input", "input()"),
        ("io:open", "open()"),
        ("builtins:isinstance", "isinstance()"),
        ("builtins:type", "type()"),
        ("grades:average", "grades.average()"),
    ],
)
def test_callee_short(callee: str, short: str):
    assert callee_short(callee) == short


def test_fill_what_uses_the_target_the_fact_and_the_derived_values():
    result = _result(_CALLS)
    fact = {
        "kind": "call",
        "callee": "builtins:print",
        "via": ["grades:helper", "messages:warn"],
        "origin_line": 12,
        "file": "messages.py",
        "line": 4,
    }
    template = (
        "{function} {file}:{line} {via_first_line} {via_last} {callee_short} "
        "{fact_file}:{fact_line} {attribute}"
    )

    text = fill_what(template, result, fact)

    assert text == "sell shop.py:8 12 messages:warn print() messages.py:4 ?"


@pytest.mark.parametrize(
    ("fact", "template", "text"),
    [
        (
            {
                "kind": "not_subclass",
                "class": "shapes:Circle",
                "expected_base": "shapes:Shape",
            },
            "{class} < {expected_base}",
            "shapes:Circle < shapes:Shape",
        ),
        (
            {"kind": "not_abstract", "concrete_methods": ["area", "describe"]},
            "{concrete_methods}",
            "area, describe",
        ),
        (
            {"kind": "instance", "creator": "pricing:total", "class": "d:Bulk"},
            "{creator} {class}",
            "pricing:total d:Bulk",
        ),
        (
            {"kind": "missing_delegation", "expected": "strategy"},
            "{expected}",
            "strategy",
        ),
    ],
)
def test_fill_what_fills_the_facts_of_hierarchy_and_strategy_markers(
    fact: dict, template: str, text: str
):
    assert fill_what(template, _result(_CALLS), fact) == text


def test_fill_what_words_the_change():
    text = fill_what("{change}", _result(_WRITES), _write("log", "mutated"))
    assert text == "changes its contents"


_DELEGATES = "DYN008/require_runtime_delegation/v1"
_BUILDS = "DYN005/forbid_runtime_instantiation/v1"


def _missing(caller: str, case: int = 0) -> dict:
    return {
        "kind": "missing_delegation",
        "case": case,
        "caller": caller,
        "expected": "self.discount",
        "raised": None,
    }


def _instance(creator: str, case: int = 0) -> dict:
    return {
        "kind": "instance",
        "case": case,
        "creator": creator,
        "class": "discounts:NoDiscount",
        "file": "pricing.py",
        "line": 8,
        "via": [],
    }


def test_classify_target_folds_a_missing_delegation_into_a_built_strategy():
    """A constructor that builds its own strategy never calls the spy, so the
    delegation check fails too: one defect, hardcoded_strategy (review of
    N5). A context of another class still misses its delegation."""
    principle = get_principle("strategy")
    built = _result(_BUILDS, [_instance("pricing:Calc.__init__")])
    missing = _result(
        _DELEGATES,
        [_missing("pricing:Calc.total"), _missing("pricing:Calc.total", 1)],
    )
    other = _result(_DELEGATES, [_missing("pricing:Shop.total")])

    findings = classify_target(principle, [missing, built, other])

    assert [
        (f.error_id, f.facts.get("caller") or f.facts.get("creator")) for f in findings
    ] == [
        ("hardcoded_strategy", "pricing:Calc.__init__"),
        ("no_delegation", "pricing:Shop.total"),
    ]
    # Without the instance, the missing delegation is the finding.
    assert [f.error_id for f in classify_target(principle, [missing])] == [
        "no_delegation"
    ]


def test_classify_target_folds_a_receiver_only_into_a_write_of_its_own_kind():
    """``a._x = b._x.setdefault(k, d)``: ``b._x`` is the receiver of a
    method that changes its contents, so it folds only into a ``mutated``
    write; the ``assigned`` write of ``a._x`` on that line is another
    object's, and b's read stays (review of N5). A rebuilt attribute
    (``obj._x = {... obj._x ...}``) folds into its ``assigned`` write."""
    principle = get_principle("encapsulation")
    assigned = _result(_WRITES, [_write("_stock", "assigned", 10)])
    mutated = _result(_WRITES, [_write("_stock", "mutated", 10)])
    by_method = _result(_READS, [{**_read("_stock", 10), "receiver": "mutated"}])
    rebuilt = _result(_READS, [{**_read("_stock", 10), "receiver": "assigned"}])

    assert [f.error_id for f in classify_target(principle, [assigned, by_method])] == [
        "replace_attribute",
        "read_private",
    ]
    assert [f.error_id for f in classify_target(principle, [mutated, by_method])] == [
        "bypass_method"
    ]
    assert [f.error_id for f in classify_target(principle, [assigned, rebuilt])] == [
        "replace_attribute"
    ]
