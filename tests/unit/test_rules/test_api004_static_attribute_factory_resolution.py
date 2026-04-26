from __future__ import annotations

from unittest.mock import Mock

from pythonarchtesting.core.models import EvalContext
from pythonarchtesting.entities import Entity, build_entity_index
from pythonarchtesting.execution.evaluators.factory_resolution import (
    filter_static_attribute_factory_candidates,
    static_attribute_factory_candidates_for_class,
)
from tests.unit.test_rules.protocol_rule_test_helpers import extract_entities


def _target_ctx(target_text: str) -> tuple[list[Entity], EvalContext]:
    target_entities = extract_entities(target_text, role="target")
    target_index = build_entity_index(target_entities)
    ctx = EvalContext(
        source_index=target_index,
        target_index=target_index,
        matches={},
        config=Mock(),
    )
    return target_entities, ctx


def _find_class(entities: list[Entity], name: str) -> Entity:
    for entity in entities:
        if entity.kind == "class" and entity.name == name:
            return entity
    raise AssertionError(f"class {name!r} not found")


def test_static_attribute_factory_resolution_discovers_class_body_annotation() -> None:
    target = """
class Target:
    INSTANCE: "Target"
"""
    target_entities, ctx = _target_ctx(target)
    target_class = _find_class(target_entities, "Target")

    candidates = static_attribute_factory_candidates_for_class(
        target_class,
        ctx,
        allow_inherited=False,
    )

    assert [candidate.name for candidate in candidates] == ["INSTANCE"]
    assert candidates[0].annotation is not None
    assert candidates[0].value_expr is None


def test_static_attribute_factory_resolution_discovers_plain_assignment() -> None:
    target = """
class Target:
    INSTANCE = object()
"""
    target_entities, ctx = _target_ctx(target)
    target_class = _find_class(target_entities, "Target")

    candidates = static_attribute_factory_candidates_for_class(
        target_class,
        ctx,
        allow_inherited=False,
    )

    assert [candidate.name for candidate in candidates] == ["INSTANCE"]
    assert candidates[0].value_expr == "object()"


def test_static_attribute_factory_resolution_ignores_archtest_marker() -> None:
    target = """
class Target:
    __archtest__ = object()
    INSTANCE = object()
"""
    target_entities, ctx = _target_ctx(target)
    target_class = _find_class(target_entities, "Target")

    candidates = static_attribute_factory_candidates_for_class(
        target_class,
        ctx,
        allow_inherited=False,
    )

    assert [candidate.name for candidate in candidates] == ["INSTANCE"]


def test_static_attribute_factory_resolution_ignores_method_wrapper_assignments() -> None:
    target = """
class Target:
    def _build_impl(cls):
        return cls()

    def _parse_impl():
        return Target()

    build = classmethod(_build_impl)
    parse = staticmethod(_parse_impl)
"""
    target_entities, ctx = _target_ctx(target)
    target_class = _find_class(target_entities, "Target")

    candidates = static_attribute_factory_candidates_for_class(
        target_class,
        ctx,
        allow_inherited=False,
    )

    assert candidates == []


def test_static_attribute_factory_resolution_finds_inherited_candidate_when_allowed() -> (
    None
):
    target = """
class Base:
    INSTANCE: "Base"

class Child(Base):
    pass
"""
    target_entities, ctx = _target_ctx(target)
    target_class = _find_class(target_entities, "Child")

    candidates = static_attribute_factory_candidates_for_class(
        target_class,
        ctx,
        allow_inherited=True,
    )

    assert [candidate.name for candidate in candidates] == ["INSTANCE"]
    assert candidates[0].owner_class.name == "Base"
    assert candidates[0].inherited is True


def test_static_attribute_factory_resolution_excludes_inherited_candidate_when_disallowed() -> (
    None
):
    target = """
class Base:
    INSTANCE: "Base"

class Child(Base):
    pass
"""
    target_entities, ctx = _target_ctx(target)
    target_class = _find_class(target_entities, "Child")

    candidates = static_attribute_factory_candidates_for_class(
        target_class,
        ctx,
        allow_inherited=False,
    )

    assert candidates == []


def test_static_attribute_factory_resolution_subclass_override_wins() -> None:
    target = """
class Base:
    INSTANCE: "Base"

class Child(Base):
    INSTANCE: "Child"
"""
    target_entities, ctx = _target_ctx(target)
    target_class = _find_class(target_entities, "Child")

    candidates = static_attribute_factory_candidates_for_class(
        target_class,
        ctx,
        allow_inherited=True,
    )

    assert [candidate.name for candidate in candidates] == ["INSTANCE"]
    assert candidates[0].owner_class.name == "Child"
    assert candidates[0].inherited is False


def test_static_attribute_factory_resolution_regex_name_filtering() -> None:
    target = """
class Target:
    current = object()
    INSTANCE = object()
"""
    target_entities, ctx = _target_ctx(target)
    target_class = _find_class(target_entities, "Target")
    candidates = static_attribute_factory_candidates_for_class(
        target_class,
        ctx,
        allow_inherited=False,
    )

    filtered = filter_static_attribute_factory_candidates(
        candidates,
        name_match="regex",
        source_name="create",
        aliases=None,
        pattern="curr.*",
    )

    assert [candidate.name for candidate in filtered] == ["current"]


def test_static_attribute_factory_resolution_alias_name_filtering() -> None:
    target = """
class Target:
    default = object()
    INSTANCE = object()
"""
    target_entities, ctx = _target_ctx(target)
    target_class = _find_class(target_entities, "Target")
    candidates = static_attribute_factory_candidates_for_class(
        target_class,
        ctx,
        allow_inherited=False,
    )

    filtered = filter_static_attribute_factory_candidates(
        candidates,
        name_match="alias",
        source_name="create",
        aliases=["INSTANCE"],
        pattern=None,
    )

    assert [candidate.name for candidate in filtered] == ["INSTANCE"]


def test_static_attribute_factory_resolution_any_name_filtering_returns_none() -> None:
    target = """
class Target:
    INSTANCE = object()
"""
    target_entities, ctx = _target_ctx(target)
    target_class = _find_class(target_entities, "Target")
    candidates = static_attribute_factory_candidates_for_class(
        target_class,
        ctx,
        allow_inherited=False,
    )

    filtered = filter_static_attribute_factory_candidates(
        candidates,
        name_match="any",
        source_name="create",
        aliases=None,
        pattern=None,
    )

    assert filtered == []
