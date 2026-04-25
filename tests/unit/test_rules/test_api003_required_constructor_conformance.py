from __future__ import annotations

from unittest.mock import Mock

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
        source_name="User",
        target_kind="class",
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


def test_api003_ctor_evaluation_fails_for_mismatched_target_explicit_init_from_dataclass_source(
) -> None:
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
