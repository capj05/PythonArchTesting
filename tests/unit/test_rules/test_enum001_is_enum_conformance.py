from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import Mock

import pytest

from pythonarchtesting.core.evaluation import evaluate_rules_for_target
from pythonarchtesting.entities import Entity, build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import MatchResult, MatchStatus
from pythonarchtesting.rules.compilation import compile_rules

RULE_ID = "ENUM001/is_enum/v1"


def _extract_modules(
    modules: list[tuple[str, str]],
    *,
    role: str,
) -> list[Entity]:
    return [
        entity
        for path, text in modules
        for entity in extract_entities_from_source(
            textwrap.dedent(text).strip() + "\n",
            Path(path),
            Path("."),
            None,
            role=role,  # type: ignore[arg-type]
            include_nested_functions=False,
            root_label=role,
        )
    ]


def _entity(
    entities: list[Entity],
    *,
    kind: str,
    module_path: str,
    name: str,
) -> Entity:
    for candidate in entities:
        if (
            candidate.kind == kind
            and candidate.module_path == module_path
            and candidate.name == name
        ):
            return candidate
    raise AssertionError(
        f"Entity not found: kind={kind!r}, module_path={module_path!r}, name={name!r}"
    )


def _matched(source: Entity, target: Entity) -> MatchResult:
    return MatchResult(
        source_id=source.canonical_id,
        status=MatchStatus.MATCHED,
        target_id=target.canonical_id,
        confidence=1.0,
        reasons=[],
        candidates=[],
    )


def _evaluate(
    *,
    source_modules: list[tuple[str, str]],
    target_modules: list[tuple[str, str]],
    target_module_path: str,
    target_name: str,
) -> tuple[list[object], list[object]]:
    source_entities = _extract_modules(source_modules, role="source")
    target_entities = _extract_modules(target_modules, role="target")

    source_entity = _entity(
        source_entities,
        kind="class",
        module_path="source_module",
        name="StatusContract",
    )
    target_entity = _entity(
        target_entities,
        kind="class",
        module_path=target_module_path,
        name=target_name,
    )
    rules, _, _ = compile_rules(source_entities, Mock())
    rule = next(
        candidate
        for candidate in rules
        if candidate.rule_id == RULE_ID
        and candidate.selector.source_entity_id == source_entity.canonical_id
    )

    return evaluate_rules_for_target(
        rules=[rule],
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches={source_entity.canonical_id: _matched(source_entity, target_entity)},
        config=Mock(),
    )


@pytest.mark.parametrize(
    ("target_source", "target_name", "expected_family"),
    [
        (
            """
from enum import Enum

class Color(Enum):
    RED = "red"
""",
            "Color",
            "enum.Enum",
        ),
        (
            """
import enum

class Color(enum.Enum):
    RED = "red"
""",
            "Color",
            "enum.Enum",
        ),
        (
            """
from enum import IntEnum

class ExitCode(IntEnum):
    OK = 0
""",
            "ExitCode",
            "enum.IntEnum",
        ),
        (
            """
from enum import StrEnum

class Status(StrEnum):
    READY = "ready"
""",
            "Status",
            "enum.StrEnum",
        ),
        (
            """
from enum import Flag, auto

class Permission(Flag):
    READ = auto()
""",
            "Permission",
            "enum.Flag",
        ),
        (
            """
from enum import IntFlag, auto

class Permission(IntFlag):
    READ = auto()
""",
            "Permission",
            "enum.IntFlag",
        ),
    ],
)
def test_enum001_evaluation_passes_for_direct_stdlib_enum_family(
    target_source: str,
    target_name: str,
    expected_family: str,
) -> None:
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import is_enum

class StatusContract:
    __archtest__: Annotated[None, is_enum()]
""",
        )
    ]
    target_modules = [("target_module.py", target_source)]

    results, errors = _evaluate(
        source_modules=source_modules,
        target_modules=target_modules,
        target_module_path="target_module",
        target_name=target_name,
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["reason"] == "recognized_direct_stdlib_enum_base"
    assert results[0].details["enum_family"] == expected_family
    assert results[0].details["detection_origin"] == "direct_stdlib_base"
    assert expected_family in results[0].details["target_bases"]


def test_enum001_evaluation_passes_for_transitive_local_enum_subclass() -> None:
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import is_enum

class StatusContract:
    __archtest__: Annotated[None, is_enum()]
""",
        )
    ]
    target_modules = [
        (
            "target_module.py",
            """
from enum import Enum

class BaseStatus(Enum):
    OK = "ok"


class DeploymentStatus(BaseStatus):
    READY = "ready"
""",
        )
    ]

    results, errors = _evaluate(
        source_modules=source_modules,
        target_modules=target_modules,
        target_module_path="target_module",
        target_name="DeploymentStatus",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["reason"] == "recognized_transitive_enum_base"
    assert results[0].details["enum_family"] == "enum.Enum"
    assert results[0].details["detection_origin"] == "transitive_local_enum_base"
    assert results[0].details["target_bases"] == ["target_module.BaseStatus"]


def test_enum001_evaluation_passes_for_mixed_inheritance_when_any_branch_is_enum_like(
) -> None:
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import is_enum

class StatusContract:
    __archtest__: Annotated[None, is_enum()]
""",
        )
    ]
    target_modules = [
        (
            "target_module.py",
            """
from enum import Enum

class SomeMixin:
    pass


class TaggedStatus(SomeMixin, Enum):
    A = "a"
""",
        )
    ]

    results, errors = _evaluate(
        source_modules=source_modules,
        target_modules=target_modules,
        target_module_path="target_module",
        target_name="TaggedStatus",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["enum_family"] == "enum.Enum"
    assert results[0].details["target_bases"] == [
        "target_module.SomeMixin",
        "enum.Enum",
    ]


@pytest.mark.parametrize(
    ("target_source", "target_name", "expected_bases"),
    [
        (
            """
class PlainStatus:
    pass
""",
            "PlainStatus",
            [],
        ),
        (
            """
class BaseStatus:
    pass


class DeploymentStatus(BaseStatus):
    READY = "ready"
""",
            "DeploymentStatus",
            ["target_module.BaseStatus"],
        ),
        (
            """
from vendor.enums import ExternalEnum

class Weird(ExternalEnum):
    pass
""",
            "Weird",
            ["vendor.enums.ExternalEnum"],
        ),
        (
            """
class Status:
    OK = "ok"
    FAIL = "fail"
""",
            "Status",
            [],
        ),
    ],
)
def test_enum001_evaluation_fails_for_non_enum_targets(
    target_source: str,
    target_name: str,
    expected_bases: list[str],
) -> None:
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import is_enum

class StatusContract:
    __archtest__: Annotated[None, is_enum()]
""",
        )
    ]
    target_modules = [("target_module.py", target_source)]

    results, errors = _evaluate(
        source_modules=source_modules,
        target_modules=target_modules,
        target_module_path="target_module",
        target_name=target_name,
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["reason"] == "target_class_is_not_enum_like"
    assert results[0].details["enum_family"] is None
    assert results[0].details["target_bases"] == expected_bases
