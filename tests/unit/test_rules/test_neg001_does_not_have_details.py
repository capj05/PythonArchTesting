"""Characterisation tests for the shape of NEG001 result details.

The details dictionary is written into the JSON report as is, so these tests
pin its key order, the keys that only the final result carries and the order
in which hits are listed.
"""

from __future__ import annotations

import dataclasses
from typing import Any
from unittest.mock import Mock

from pythonarchtesting.core.models import EvalContext
from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.execution.evaluators.member_absence import (
    MemberAbsenceEvaluator,
)
from pythonarchtesting.rules.compilation import compile_rules
from tests.unit.test_rules.protocol_rule_test_helpers import (
    evaluate_single_rule,
    extract_entities,
    match_for,
)

_BASE_KEYS = [
    "reason",
    "forbidden_member",
    "hits",
    "match_status",
    "name_match",
    "signature_mode",
]


def _evaluate(marker: str, target: str) -> Any:
    """Evaluate one ``does_not_have`` marker against a ``User`` target class."""
    source = f"""
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[None, {marker}]
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
    )
    assert errors == []
    assert len(results) == 1
    return results[0]


def _evaluate_direct(params: dict[str, Any], target: str) -> Any:
    """Call the evaluator directly with hand-written rule parameters.

    The compiler normalises and validates parameters, so states that only a
    hand-built rule can reach are exercised by bypassing it here.
    """
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[None, does_not_have("placeholder")]
"""
    source_entities = extract_entities(source, role="source")
    target_entities = extract_entities(target, role="target")
    rules, _, _ = compile_rules(source_entities, Mock())
    rule = dataclasses.replace(rules[0], params=params)
    source_entity = next(e for e in source_entities if e.kind == "class")
    target_entity = next(e for e in target_entities if e.kind == "class")
    ctx = EvalContext(
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches={},
        config=Mock(),
        source_by_id={e.canonical_id: e for e in source_entities},
    )
    match = match_for(source_entity, target_entity)[source_entity.canonical_id]
    return MemberAbsenceEvaluator().evaluate(
        rule, source_entity, target_entity, match, ctx
    )


def test_neg001_regex_details_keep_key_order_and_strip_the_pattern() -> None:
    result = _evaluate(
        'does_not_have(name_match="regex", pattern="  debug_.+  ")',
        """
class User:
    def debug_dump(self) -> None:
        return None
""",
    )

    assert result.status == "FAILED"
    assert list(result.details) == [*_BASE_KEYS, "pattern"]
    assert result.details["pattern"] == "debug_.+"
    assert list(result.details["forbidden_member"]) == [
        "name",
        "member_kind",
        "storage",
        "declared_only",
    ]


def test_neg001_alias_details_append_aliases_after_the_base_keys() -> None:
    result = _evaluate(
        'does_not_have("dump", name_match="alias", aliases=["dump", "trace"])',
        """
class User:
    def save(self) -> None:
        return None
""",
    )

    assert result.status == "OK"
    assert list(result.details) == [*_BASE_KEYS, "aliases"]
    assert result.details["aliases"] == ["dump", "trace"]


def test_neg001_missing_signature_anchor_omits_aliases_and_pattern() -> None:
    result = _evaluate_direct(
        {
            "name_match": "regex",
            "pattern": "debug_.+",
            "aliases": ["debug_dump"],
            "signature_mode": "exact",
            "signature_anchor_entity_id": "missing-anchor",
        },
        """
class User:
    def debug_dump(self) -> None:
        return None
""",
    )

    assert result.status == "FAILED"
    assert result.details["reason"] == (
        "missing source signature anchor for forbidden method check"
    )
    assert list(result.details) == _BASE_KEYS


def test_neg001_evaluator_strips_a_pattern_the_compiler_left_unstripped() -> None:
    result = _evaluate_direct(
        {"name_match": "regex", "pattern": "  debug_.+  ", "aliases": "dump"},
        """
class User:
    def debug_dump(self) -> None:
        return None
""",
    )

    assert result.status == "FAILED"
    assert list(result.details) == [*_BASE_KEYS, "pattern"]
    assert result.details["pattern"] == "debug_.+"


def test_neg001_hits_list_declared_members_before_inherited_ones() -> None:
    result = _evaluate(
        'does_not_have(name_match="regex", pattern="token|dump")',
        """
class Base:
    token: str = "t"

class User(Base):
    def dump(self) -> None:
        return None

    def __init__(self) -> None:
        self.token: str = "u"
""",
    )

    assert result.status == "FAILED"
    assert [
        (hit["name"], hit["member_kind"], hit["storage"], hit["inherited"])
        for hit in result.details["hits"]
    ] == [
        ("dump", "method", None, False),
        ("token", "attribute", "instance", False),
        ("token", "attribute", "class", True),
    ]
