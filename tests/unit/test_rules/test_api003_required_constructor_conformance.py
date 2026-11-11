from __future__ import annotations

from unittest.mock import Mock

import pytest

from pythonarchtesting.core.evaluation import evaluate_rules_for_target
from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.matching import MatchResult, MatchStatus
from pythonarchtesting.rules.compilation import compile_rules
from tests.unit.test_rules.protocol_rule_test_helpers import (
    evaluate_single_rule,
    extract_entities,
)


def test_api003_ctor_evaluation_passes_for_compatible_init() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[None, required_constructor()]

    def __init__(self, name: str) -> None:
        self.name = name
"""
    target = """
class User:
    def __init__(self, name: str) -> None:
        self.name = name
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_constructor/v1",
    )
    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["constructor"]["resolved_kind"] == "__init__"
    assert results[0].details["member_origin"] == "declared"
    assert results[0].details["resolved_target_constructor"] == "__init__"


def test_api003_ctor_evaluation_allows_extra_params_in_compatible_mode() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[None, required_constructor()]

    def __init__(self, name: str) -> None:
        self.name = name
"""
    target = """
class User:
    def __init__(self, name: str, age: int = 0) -> None:
        self.name = name
        self.age = age
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_constructor/v1",
    )
    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api003_ctor_evaluation_fails_for_missing_required_param() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[None, required_constructor()]

    def __init__(self, name: str, email: str) -> None:
        self.name = name
        self.email = email
"""
    target = """
class User:
    def __init__(self, name: str) -> None:
        self.name = name
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_constructor/v1",
    )
    assert errors == []
    assert [result.status for result in results] == ["FAILED"]


def test_api003_optional_ctor_evaluation_still_passes_for_compatible_init() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[None, required_constructor(allow_missing=True)]

    def __init__(self, name: str) -> None:

        self.name = name
"""
    target = """
class User:
    def __init__(self, name: str) -> None:
        self.name = name
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_constructor/v1",
    )
    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api003_optional_ctor_evaluation_still_fails_for_incompatible_signature() -> (
    None
):
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[None, required_constructor(allow_missing=True)]

    def __init__(self, name: str, email: str) -> None:
        self.name = name
        self.email = email
"""
    target = """
class User:
    def __init__(self, name: str) -> None:
        self.name = name
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_constructor/v1",
    )
    assert errors == []
    assert [result.status for result in results] == ["FAILED"]


def test_api003_ctor_any_mode_passes_when_constructor_exists_with_mismatched_params() -> (
    None
):
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[None, required_constructor(signature_mode="any")]

    def __init__(self, name: str, email: str) -> None:
        self.name = name
        self.email = email
"""
    target = """
class User:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_constructor/v1",
    )
    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["params_ignored"] is True
    assert results[0].details["resolved_target_constructor"] == "__init__"


def test_api003_ctor_evaluation_passes_for_source_dataclass_against_explicit_init() -> (
    None
):
    source = """
from dataclasses import dataclass
from typing import Annotated
from pythonarchtesting.rules import required_constructor

@dataclass
class User:
    __archtest__: Annotated[None, required_constructor()]
    name: str
    email: str | None = None
"""
    target = """
class User:
    def __init__(self, name: str, email: str | None = None) -> None:
        self.name = name
        self.email = email
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        target_kind="class",
        source_name="User",
        target_name="User",
        rule_id="API003/required_constructor/v2",
    )
    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["resolved_target_constructor"] == "__init__"
    assert results[0].details["member_origin"] == "declared"


def test_api003_ctor_evaluation_passes_for_source_and_target_dataclass_generated_init() -> (
    None
):
    source = """
from dataclasses import dataclass
from typing import Annotated
from pythonarchtesting.rules import required_constructor

@dataclass
class User:
    __archtest__: Annotated[None, required_constructor()]
    name: str
    email: str | None = None
"""
    target = """
from dataclasses import dataclass

@dataclass
class User:
    name: str
    email: str | None = None
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_constructor/v2",
    )
    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["resolved_target_constructor"] == "__init__"


def test_api003_ctor_evaluation_fails_for_mismatched_target_explicit_init_from_dataclass_source() -> (  # noqa: E501
    None
):
    source = """
from dataclasses import dataclass
from typing import Annotated
from pythonarchtesting.rules import required_constructor

@dataclass
class User:
    __archtest__: Annotated[None, required_constructor()]
    name: str
    email: str
"""
    target = """
class User:
    def __init__(self, name: str) -> None:
        self.name = name
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_constructor/v2",
    )
    assert errors == []
    assert [result.status for result in results] == ["FAILED"]


def test_api003_ctor_evaluation_fails_when_init_required_but_target_only_has_new() -> (
    None
):
    source = """
from dataclasses import dataclass
from typing import Annotated
from pythonarchtesting.rules import required_constructor

@dataclass
class User:
    __archtest__: Annotated[
        None, required_constructor(constructor_kind="__init__")
    ]
    name: str
"""
    target = """
class User:
    def __new__(cls, name: str) -> "User":
        return super().__new__(cls)
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_constructor/v2",
    )
    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "missing_constructor"


def test_api003_ctor_evaluation_passes_for_inherited_when_allowed() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class Child:
    __archtest__: Annotated[None, required_constructor()]

    def __init__(self, name: str) -> None:
        self.name = name
"""
    target = """
class Base:
    def __init__(self, name: str) -> None:
        self.name = name


class Child(Base):
    pass
"""
    source_entities = extract_entities(source, role="source")
    target_entities = extract_entities(target, role="target")
    source_class = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Child"
    )
    target_class = next(
        entity
        for entity in target_entities
        if entity.kind == "class" and entity.name == "Child"
    )

    rules, _, _ = compile_rules(source_entities, Mock())
    matches = {
        source_class.canonical_id: MatchResult(
            source_id=source_class.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_class.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["member_origin"] == "inherited"


def test_api003_ctor_evaluation_dataclass_base_generated_init_passes_when_inherited_allowed() -> (
    None
):
    source = """
from dataclasses import dataclass
from typing import Annotated
from pythonarchtesting.rules import required_constructor

@dataclass
class Child:
    __archtest__: Annotated[None, required_constructor()]
    name: str
"""
    target = """
from dataclasses import dataclass

@dataclass
class Base:
    name: str

class Child(Base):
    pass
"""
    source_entities = extract_entities(source, role="source")
    target_entities = extract_entities(target, role="target")
    source_class = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Child"
    )
    target_class = next(
        entity
        for entity in target_entities
        if entity.kind == "class" and entity.name == "Child"
    )

    rules, _, _ = compile_rules(source_entities, Mock())
    matches = {
        source_class.canonical_id: MatchResult(
            source_id=source_class.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_class.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["member_origin"] == "inherited"


def test_api003_ctor_evaluation_fails_for_inherited_when_not_allowed() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class Child:
    __archtest__: Annotated[
        None, required_constructor(allow_inherited=False)
    ]

    def __init__(self, name: str) -> None:
        self.name = name
"""
    target = """
class Base:
    def __init__(self, name: str) -> None:
        self.name = name


class Child(Base):
    pass
"""
    source_entities = extract_entities(source, role="source")
    target_entities = extract_entities(target, role="target")
    source_class = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Child"
    )
    target_class = next(
        entity
        for entity in target_entities
        if entity.kind == "class" and entity.name == "Child"
    )

    rules, _, _ = compile_rules(source_entities, Mock())
    matches = {
        source_class.canonical_id: MatchResult(
            source_id=source_class.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_class.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "constructor_inherited_not_allowed"
    assert results[0].details["member_origin"] == "inherited"


def test_api003_ctor_evaluation_dataclass_base_generated_init_fails_when_inherited_disallowed() -> (
    None
):
    source = """
from dataclasses import dataclass
from typing import Annotated
from pythonarchtesting.rules import required_constructor

@dataclass
class Child:
    __archtest__: Annotated[
        None, required_constructor(allow_inherited=False)
    ]
    name: str
"""
    target = """
from dataclasses import dataclass

@dataclass
class Base:
    name: str

class Child(Base):
    pass
"""
    source_entities = extract_entities(source, role="source")
    target_entities = extract_entities(target, role="target")
    source_class = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Child"
    )
    target_class = next(
        entity
        for entity in target_entities
        if entity.kind == "class" and entity.name == "Child"
    )

    rules, _, _ = compile_rules(source_entities, Mock())
    matches = {
        source_class.canonical_id: MatchResult(
            source_id=source_class.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_class.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "constructor_inherited_not_allowed"
    assert results[0].details["member_origin"] == "inherited"


def test_api003_optional_ctor_evaluation_skips_for_inherited_when_not_allowed() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class Child:
    __archtest__: Annotated[
        None, required_constructor(allow_inherited=False, allow_missing=True)
    ]

    def __init__(self, name: str) -> None:
        self.name = name
"""
    target = """
class Base:
    def __init__(self, name: str) -> None:
        self.name = name


class Child(Base):
    pass
"""
    source_entities = extract_entities(source, role="source")
    target_entities = extract_entities(target, role="target")
    source_class = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Child"
    )
    target_class = next(
        entity
        for entity in target_entities
        if entity.kind == "class" and entity.name == "Child"
    )

    rules, _, _ = compile_rules(source_entities, Mock())
    matches = {
        source_class.canonical_id: MatchResult(
            source_id=source_class.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_class.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["SKIPPED"]
    assert results[0].details["failure_reason"] == "optional_member_absent"


def test_api003_ctor_evaluation_fails_when_class_unmatched() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[None, required_constructor()]

    def __init__(self, name: str) -> None:
        self.name = name
"""
    source_entities = extract_entities(source, role="source")
    source_class = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "User"
    )

    rules, _, _ = compile_rules(source_entities, Mock())

    matches = {
        source_class.canonical_id: MatchResult(
            source_id=source_class.canonical_id,
            status=MatchStatus.UNMATCHED,
            target_id=None,
            confidence=0.2,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index([]),
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]


def test_api003_ctor_evaluation_fails_when_target_has_no_constructor() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[
        None, required_constructor(allow_inherited=False)
    ]

    def __init__(self, name: str) -> None:
        self.name = name
"""
    target = """
class User:
    pass
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_constructor/v1",
    )
    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "missing_constructor"


def test_api003_optional_ctor_evaluation_skips_when_target_has_no_constructor() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[
        None, required_constructor(allow_inherited=False, allow_missing=True)
    ]

    def __init__(self, name: str) -> None:
        self.name = name
"""
    target = """
class User:
    pass
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_constructor/v1",
    )
    assert errors == []
    assert [result.status for result in results] == ["SKIPPED"]
    assert results[0].details["failure_reason"] == "optional_member_absent"


_INIT_SOURCE = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[None, required_constructor()]

    def __init__(self, name: str) -> None:
        self.name = name
"""

_DATACLASS_SOURCE = """
from dataclasses import dataclass
from typing import Annotated
from pythonarchtesting.rules import required_constructor

@dataclass
class User:
    __archtest__: Annotated[None, required_constructor()]
    name: str
"""

_INIT_TARGET = """
class User:
    def __init__(self, name: str) -> None:
        self.name = name
"""


def _evaluate_ctor_rule(
    source: str,
    target: str,
    *,
    target_kind: str = "class",
    params: dict[str, object] | None = None,
    drop: tuple[str, ...] = (),
) -> object:
    """Evaluate the compiled constructor rule with some parameters changed.

    The compiler always resolves a source constructor, so the branches that
    handle a missing or unusable one are reached only by editing the
    compiled parameters, as a hand-written or stale rule would have them.
    """
    source_entities = extract_entities(source, role="source")
    target_entities = extract_entities(target, role="target")
    source_class = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "User"
    )
    target_entity = next(
        entity
        for entity in target_entities
        if entity.kind == target_kind and entity.name == "User"
    )
    rules, _, _ = compile_rules(source_entities, Mock())
    rule = next(rule for rule in rules if rule.name == "required_constructor")
    for name in drop:
        rule.params.pop(name, None)
    rule.params.update(params or {})
    results, errors = evaluate_rules_for_target(
        rules=[rule],
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches={
            source_class.canonical_id: MatchResult(
                source_id=source_class.canonical_id,
                status=MatchStatus.MATCHED,
                target_id=target_entity.canonical_id,
                confidence=1.0,
                reasons=[],
                candidates=[],
            )
        },
        config=Mock(),
        source_by_id={entity.canonical_id: entity for entity in source_entities},
        target_by_id={entity.canonical_id: entity for entity in target_entities},
    )
    assert errors == []
    assert len(results) == 1
    return results[0]


def test_api003_ctor_evaluation_fails_when_the_match_is_not_a_class() -> None:
    target = """
def User(name: str) -> None:
    pass
"""
    result = _evaluate_ctor_rule(_INIT_SOURCE, target, target_kind="function")

    assert result.status == "FAILED"
    assert ":User:function:" in result.target_entity_id
    assert result.details == {
        "reason": "required_constructor requires a matched target class",
        "errors": ["required_constructor requires a matched target class"],
        "mode": "compatible",
        # Unlike every other branch, this one reports no "params_ignored".
        "check_return": False,
        "allow_missing": False,
        "constructor": {
            "kind": "auto",
            "resolved_kind": "__init__",
            "allow_inherited": True,
            "allow_missing": False,
        },
        "resolved_target_constructor": None,
        "member_origin": "missing",
    }


@pytest.mark.parametrize(
    ("source", "params", "drop"),
    [
        # No constructor id and no model: nothing to compare against.
        (_INIT_SOURCE, {}, ("expected_source_constructor_id",)),
        # An id that resolves to no entity at all.
        (_INIT_SOURCE, {"expected_source_constructor_id": "missing"}, ()),
        # A model whose context is not a class.
        (
            _DATACLASS_SOURCE,
            {"expected_source_constructor_context_id": "missing"},
            (),
        ),
        # A context class without a usable model.
        (
            _DATACLASS_SOURCE,
            {"expected_source_constructor_model": "not a model"},
            (),
        ),
    ],
)
def test_api003_ctor_evaluation_fails_without_a_resolved_source_constructor(
    source: str, params: dict[str, object], drop: tuple[str, ...]
) -> None:
    result = _evaluate_ctor_rule(source, _INIT_TARGET, params=params, drop=drop)

    assert result.status == "FAILED"
    assert result.target_entity_id.endswith("User:class:-")
    reason = "compiler did not resolve a source constructor for required_constructor"
    assert result.details["reason"] == reason
    assert result.details["errors"] == [reason]
    assert list(result.details) == [
        "reason",
        "errors",
        "mode",
        "params_ignored",
        "check_return",
        "allow_missing",
        "constructor",
        "resolved_target_constructor",
        "member_origin",
    ]
    assert result.details["member_origin"] == "missing"


def test_api003_ctor_evaluation_falls_back_to_the_model_for_a_non_method_id() -> None:
    source_class_id = next(
        entity.canonical_id
        for entity in extract_entities(_DATACLASS_SOURCE, role="source")
        if entity.kind == "class" and entity.name == "User"
    )
    result = _evaluate_ctor_rule(
        _DATACLASS_SOURCE,
        _INIT_TARGET,
        params={"expected_source_constructor_id": source_class_id},
    )

    assert result.status == "OK"
    assert result.details["reason"] == "Required constructor satisfied."
    assert result.details["resolved_target_constructor"] == "__init__"


def test_api003_ctor_evaluation_reports_details_in_a_fixed_order() -> None:
    target = """
class User:
    def __init__(self, other: int) -> None:
        self.other = other
"""
    failed = _evaluate_ctor_rule(_INIT_SOURCE, target)
    missing = _evaluate_ctor_rule(_INIT_SOURCE, "class User:\n    pass\n")

    assert failed.status == "FAILED"
    assert list(failed.details) == [
        "reason",
        "errors",
        "expected",
        "found",
        "mode",
        "params_ignored",
        "check_return",
        "allow_missing",
        "constructor",
        "resolved_target_constructor",
        "member_origin",
    ]
    assert missing.status == "FAILED"
    assert list(missing.details)[-1] == "failure_reason"
    assert missing.details["failure_reason"] == "missing_constructor"
