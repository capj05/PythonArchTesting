from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.core.evaluation import evaluate_rules_for_target
from pythonarchtesting.entities import Entity, build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import MatchResult, MatchStatus
from pythonarchtesting.rules.compilation import compile_rules


def _extract_entities(source_text: str, *, role: str) -> list[Entity]:
    return extract_entities_from_source(
        source_text=source_text,
        file_path=Path(f"{role}_module.py"),
        root_path=Path("."),
        target_module_name=None,
        role=role,  # type: ignore[arg-type]
        include_nested_functions=False,
        root_label=role,
    )


def _find(entities: list[Entity], *, kind: str, name: str) -> Entity:
    for entity in entities:
        if entity.kind == kind and entity.name == name:
            return entity
    raise AssertionError(
        f"Entity '{name}' ({kind}) not found; available: "
        f"{[(entity.kind, entity.name) for entity in entities]}"
    )


def _evaluate_factory_rule(
    source_text: str,
    target_text: str,
    *,
    source_method_name: str,
    source_class_name: str,
    target_class_name: str,
    rule_id: str = "API004/required_factory/v1",
) -> tuple[list[object], list[object]]:
    source_entities = _extract_entities(source_text, role="source")
    target_entities = _extract_entities(target_text, role="target")

    source_method = _find(source_entities, kind="method", name=source_method_name)
    source_class = _find(source_entities, kind="class", name=source_class_name)
    target_class = _find(target_entities, kind="class", name=target_class_name)

    rules, _, _ = compile_rules(source_entities, Mock())
    selected_rules = [rule for rule in rules if rule.rule_id == rule_id]

    matches: dict[str, MatchResult] = {
        source_method.canonical_id: MatchResult(
            source_id=source_method.canonical_id,
            status=MatchStatus.UNMATCHED,
            target_id=None,
            confidence=0.0,
            reasons=[],
            candidates=[],
        ),
        source_class.canonical_id: MatchResult(
            source_id=source_class.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_class.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
    }

    results, errors = evaluate_rules_for_target(
        rules=selected_rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches=matches,
        config=Mock(),
        source_by_id={entity.canonical_id: entity for entity in source_entities},
        target_by_id={entity.canonical_id: entity for entity in target_entities},
    )
    return results, errors


def test_api004_pass_source_init_satisfied_by_target_init() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyService:
    def __init__(self, name: str, value: int):
        __archtest__: Annotated[None, required_factory()]
        self.name = name
        self.value = value
"""
    target = """
class MyService:
    def __init__(self, name: str, value: int):
        self.name = name
        self.value = value
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="__init__",
        source_class_name="MyService",
        target_class_name="MyService",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api004_pass_source_init_satisfied_by_target_dataclass_constructor() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyService:
    def __init__(self, name: str, enabled: bool = True):
        __archtest__: Annotated[
            None, required_factory(satisfy_with=("constructor",))
        ]
        self.name = name
        self.enabled = enabled
"""
    target = """
from dataclasses import dataclass

@dataclass
class MyService:
    name: str
    enabled: bool = True
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="__init__",
        source_class_name="MyService",
        target_class_name="MyService",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api004_pass_source_init_satisfied_by_target_classmethod() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyService:
    def __init__(self, name: str):
        __archtest__: Annotated[None, required_factory(satisfy_with=("classmethod",))]
        self.name = name
"""
    target = """
class MyService:
    @classmethod
    def create(cls, name: str):
        return cls()
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="__init__",
        source_class_name="MyService",
        target_class_name="MyService",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api004_pass_mixed_factory_rule_uses_dataclass_constructor_resolution() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyService:
    def __init__(self, name: str, enabled: bool = True):
        __archtest__: Annotated[
            None,
            required_factory(
                satisfy_with=("constructor", "classmethod"),
                name_match="exact",
            ),
        ]
        self.name = name
        self.enabled = enabled
"""
    target = """
from dataclasses import dataclass

@dataclass
class MyService:
    name: str
    enabled: bool = True

    @classmethod
    def create(cls, name: str):
        return cls(name=name)
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="__init__",
        source_class_name="MyService",
        target_class_name="MyService",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api004_optional_factory_passes_when_candidate_is_present() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyService:
    def __init__(self, name: str):
        __archtest__: Annotated[
            None, required_factory(satisfy_with=("classmethod",), allow_missing=True)
        ]
        self.name = name
"""
    target = """
class MyService:
    @classmethod
    def create(cls, name: str):
        return cls()
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="__init__",
        source_class_name="MyService",
        target_class_name="MyService",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api004_pass_allow_inherited_true_finds_inherited_constructor() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class Base:
    def __init__(self, name: str):
        __archtest__: Annotated[
            None,
            required_factory(satisfy_with=("constructor",), allow_inherited=True),
        ]
        self.name = name
"""
    target = """
class Base:
    def __init__(self, name: str):
        self.name = name

class Child(Base):
    pass
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="__init__",
        source_class_name="Base",
        target_class_name="Child",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api004_fail_no_factory_candidate_found() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyService:
    def __init__(self, x: int):
        __archtest__: Annotated[None, required_factory(satisfy_with=("classmethod",))]
        self.x = x
"""
    target = """
class MyService:
    def process(self):
        pass
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="__init__",
        source_class_name="MyService",
        target_class_name="MyService",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["reason"] == "no_factory_candidate_found"


def test_api004_optional_factory_skips_when_no_candidate_found() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyService:
    def __init__(self, x: int):
        __archtest__: Annotated[
            None,
            required_factory(
                satisfy_with=("classmethod",),
                allow_missing=True,
            ),
        ]
        self.x = x
"""
    target = """
class MyService:
    def process(self):
        pass
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="__init__",
        source_class_name="MyService",
        target_class_name="MyService",
    )

    assert errors == []
    assert [result.status for result in results] == ["SKIPPED"]
    assert results[0].details["failure_reason"] == "optional_member_absent"


def test_api004_fail_candidates_exist_but_signatures_incompatible() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyService:
    def __init__(self, name: str, value: int):
        __archtest__: Annotated[None, required_factory(satisfy_with=("constructor",))]
        self.name = name
        self.value = value
"""
    target = """
class MyService:
    def __init__(self, x: int):
        self.x = x
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="__init__",
        source_class_name="MyService",
        target_class_name="MyService",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["reason"] == "no_compatible_factory_candidate"


def test_api004_optional_factory_still_fails_for_incompatible_signature() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyService:
    def __init__(self, name: str, value: int):
        __archtest__: Annotated[
            None,
            required_factory(
                satisfy_with=("constructor",),
                allow_missing=True,
            ),
        ]
        self.name = name
        self.value = value
"""
    target = """
class MyService:
    def __init__(self, x: int):
        self.x = x
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="__init__",
        source_class_name="MyService",
        target_class_name="MyService",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["reason"] == "no_compatible_factory_candidate"


def test_api004_fail_multiple_compatible_candidates_is_ambiguous() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyService:
    def __init__(self, name: str):
        __archtest__: Annotated[
            None,
            required_factory(satisfy_with=("classmethod",), name_match="any"),
        ]
        self.name = name
"""
    target = """
class MyService:
    @classmethod
    def create(cls, name: str):
        return cls()

    @classmethod
    def from_string(cls, name: str):
        return cls()
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="__init__",
        source_class_name="MyService",
        target_class_name="MyService",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["reason"] == "multiple_compatible_factory_candidates"


def test_api004_optional_factory_any_name_still_fails_when_candidate_is_incompatible() -> (
    None
):
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyService:
    def __init__(self, name: str, value: int):
        __archtest__: Annotated[
            None,
            required_factory(
                satisfy_with=("classmethod",),
                name_match="any",
                allow_missing=True,
            ),
        ]
        self.name = name
        self.value = value
"""
    target = """
class MyService:
    @classmethod
    def create(cls, name: str):
        return cls()
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="__init__",
        source_class_name="MyService",
        target_class_name="MyService",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["reason"] == "no_compatible_factory_candidate"


def test_api004_optional_factory_alias_skips_when_alias_candidate_missing() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class Session:
    @classmethod
    def create(cls, user_id: str):
        __archtest__: Annotated[
            None,
            required_factory(
                satisfy_with=("classmethod",),
                name_match="alias",
                aliases=["build"],
                allow_missing=True,
            ),
        ]
        return cls()
"""
    target = """
class Session:
    @classmethod
    def create(cls, user_id: str):
        return cls()
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="create",
        source_class_name="Session",
        target_class_name="Session",
    )

    assert errors == []
    assert [result.status for result in results] == ["SKIPPED"]
    assert results[0].details["failure_reason"] == "optional_member_absent"


def test_api004_optional_factory_regex_skips_when_pattern_candidate_missing() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class Session:
    @classmethod
    def create(cls, user_id: str):
        __archtest__: Annotated[
            None,
            required_factory(
                satisfy_with=("classmethod",),
                name_match="regex",
                pattern="from_.*",
                allow_missing=True,
            ),
        ]
        return cls()
"""
    target = """
class Session:
    @classmethod
    def create(cls, user_id: str):
        return cls()
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="create",
        source_class_name="Session",
        target_class_name="Session",
    )

    assert errors == []
    assert [result.status for result in results] == ["SKIPPED"]
    assert results[0].details["failure_reason"] == "optional_member_absent"


def test_api004_optional_factory_skips_for_inherited_candidate_when_not_allowed() -> (
    None
):
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class Base:
    def __init__(self, name: str):
        __archtest__: Annotated[
            None,
            required_factory(
                satisfy_with=("constructor",),
                allow_inherited=False,
                allow_missing=True,
            ),
        ]
        self.name = name
"""
    target = """
class Base:
    def __init__(self, name: str):
        self.name = name

class Child(Base):
    pass
"""
    results, errors = _evaluate_factory_rule(
        source,
        target,
        source_method_name="__init__",
        source_class_name="Base",
        target_class_name="Child",
    )

    assert errors == []
    assert [result.status for result in results] == ["SKIPPED"]
    assert results[0].details["failure_reason"] == "optional_member_absent"
