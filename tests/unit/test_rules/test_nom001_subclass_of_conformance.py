from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.core.evaluation import evaluate_rules_for_target
from pythonarchtesting.entities import Entity, build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import MatchResult, MatchStatus
from pythonarchtesting.rules.compilation import compile_rules


def _extract_entities(
    source_text: str,
    *,
    role: str,
    path: str,
) -> list[Entity]:
    return extract_entities_from_source(
        textwrap.dedent(source_text).strip() + "\n",
        Path(path),
        Path("."),
        None,
        role=role,  # type: ignore[arg-type]
        include_nested_functions=False,
        root_label=role,
    )


def _entity(
    entities: list[Entity],
    *,
    kind: str,
    module_path: str,
    name: str,
) -> Entity:
    for entity in entities:
        if (
            entity.kind == kind
            and entity.module_path == module_path
            and entity.name == name
        ):
            return entity
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


def _match_with_status(source: Entity, status: MatchStatus) -> MatchResult:
    return MatchResult(
        source_id=source.canonical_id,
        status=status,
        target_id=None,
        confidence=0.0,
        reasons=[],
        candidates=[],
    )


def _evaluate(
    *,
    source_modules: list[tuple[str, str]],
    target_modules: list[tuple[str, str]],
    source_module_path: str,
    matches: list[MatchResult],
) -> tuple[list[object], list[object]]:
    source_entities = [
        entity
        for path, text in source_modules
        for entity in _extract_entities(text, role="source", path=path)
    ]
    target_entities = [
        entity
        for path, text in target_modules
        for entity in _extract_entities(text, role="target", path=path)
    ]

    source_entity = _entity(
        source_entities,
        kind="class",
        module_path=source_module_path,
        name="CsvRepository",
    )
    rules, _, _ = compile_rules(source_entities, Mock())
    rule = next(
        rule
        for rule in rules
        if rule.rule_id == "NOM001/subclass_of/v1"
        and rule.selector.source_entity_id == source_entity.canonical_id
    )

    results, errors = evaluate_rules_for_target(
        rules=[rule],
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches={match.source_id: match for match in matches},
        config=Mock(),
    )
    return results, errors


def test_nom001_evaluation_passes_for_direct_subclass_of_matched_target_base() -> None:
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import subclass_of

class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[None, subclass_of("source_module.BaseRepository")]
""",
        )
    ]
    target_modules = [
        (
            "target_module.py",
            """
class AssignmentRepositoryBase:
    pass


class CsvRepository(AssignmentRepositoryBase):
    pass
""",
        )
    ]

    source_entities = [
        entity
        for path, text in source_modules
        for entity in _extract_entities(text, role="source", path=path)
    ]
    target_entities = [
        entity
        for path, text in target_modules
        for entity in _extract_entities(text, role="target", path=path)
    ]
    source_class = _entity(
        source_entities, kind="class", module_path="source_module", name="CsvRepository"
    )
    source_base = _entity(
        source_entities,
        kind="class",
        module_path="source_module",
        name="BaseRepository",
    )
    target_class = _entity(
        target_entities, kind="class", module_path="target_module", name="CsvRepository"
    )
    target_base = _entity(
        target_entities,
        kind="class",
        module_path="target_module",
        name="AssignmentRepositoryBase",
    )

    results, errors = _evaluate(
        source_modules=source_modules,
        target_modules=target_modules,
        source_module_path="source_module",
        matches=[
            _matched(source_class, target_class),
            _matched(source_base, target_base),
        ],
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_nom001_evaluation_passes_for_transitive_subclass() -> None:
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import subclass_of

class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[None, subclass_of("source_module.BaseRepository")]
""",
        )
    ]
    target_modules = [
        (
            "target_module.py",
            """
class AssignmentRepositoryBase:
    pass


class IntermediateRepository(AssignmentRepositoryBase):
    pass


class CsvRepository(IntermediateRepository):
    pass
""",
        )
    ]

    source_entities = [
        entity
        for path, text in source_modules
        for entity in _extract_entities(text, role="source", path=path)
    ]
    target_entities = [
        entity
        for path, text in target_modules
        for entity in _extract_entities(text, role="target", path=path)
    ]
    source_class = _entity(
        source_entities, kind="class", module_path="source_module", name="CsvRepository"
    )
    source_base = _entity(
        source_entities,
        kind="class",
        module_path="source_module",
        name="BaseRepository",
    )
    target_class = _entity(
        target_entities, kind="class", module_path="target_module", name="CsvRepository"
    )
    target_base = _entity(
        target_entities,
        kind="class",
        module_path="target_module",
        name="AssignmentRepositoryBase",
    )

    results, errors = _evaluate(
        source_modules=source_modules,
        target_modules=target_modules,
        source_module_path="source_module",
        matches=[
            _matched(source_class, target_class),
            _matched(source_base, target_base),
        ],
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_nom001_evaluation_fails_when_expected_base_counterpart_is_unmatched() -> None:
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import subclass_of

class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[None, subclass_of("source_module.BaseRepository")]
""",
        )
    ]
    target_modules = [
        (
            "target_module.py",
            """
class CsvRepository:
    pass
""",
        )
    ]

    source_entities = [
        entity
        for path, text in source_modules
        for entity in _extract_entities(text, role="source", path=path)
    ]
    target_entities = [
        entity
        for path, text in target_modules
        for entity in _extract_entities(text, role="target", path=path)
    ]
    source_class = _entity(
        source_entities, kind="class", module_path="source_module", name="CsvRepository"
    )
    source_base = _entity(
        source_entities,
        kind="class",
        module_path="source_module",
        name="BaseRepository",
    )
    target_class = _entity(
        target_entities, kind="class", module_path="target_module", name="CsvRepository"
    )

    results, errors = _evaluate(
        source_modules=source_modules,
        target_modules=target_modules,
        source_module_path="source_module",
        matches=[
            _matched(source_class, target_class),
            _match_with_status(source_base, MatchStatus.UNMATCHED),
        ],
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "required base counterpart is not available" in results[0].message


def test_nom001_evaluation_fails_when_target_ancestry_does_not_include_matched_base() -> (
    None
):
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import subclass_of

class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[None, subclass_of("source_module.BaseRepository")]
""",
        )
    ]
    target_modules = [
        (
            "target_module.py",
            """
class AssignmentRepositoryBase:
    pass


class OtherBase:
    pass


class CsvRepository(OtherBase):
    pass
""",
        )
    ]

    source_entities = [
        entity
        for path, text in source_modules
        for entity in _extract_entities(text, role="source", path=path)
    ]
    target_entities = [
        entity
        for path, text in target_modules
        for entity in _extract_entities(text, role="target", path=path)
    ]
    source_class = _entity(
        source_entities, kind="class", module_path="source_module", name="CsvRepository"
    )
    source_base = _entity(
        source_entities,
        kind="class",
        module_path="source_module",
        name="BaseRepository",
    )
    target_class = _entity(
        target_entities, kind="class", module_path="target_module", name="CsvRepository"
    )
    target_base = _entity(
        target_entities,
        kind="class",
        module_path="target_module",
        name="AssignmentRepositoryBase",
    )

    results, errors = _evaluate(
        source_modules=source_modules,
        target_modules=target_modules,
        source_module_path="source_module",
        matches=[
            _matched(source_class, target_class),
            _matched(source_base, target_base),
        ],
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert (
        "target ancestry does not contain the matched counterpart" in results[0].message
    )


def test_nom001_evaluation_rejects_same_named_unrelated_target_base() -> None:
    source_modules = [
        (
            "reference/base.py",
            """
class BaseRepository:
    pass
""",
        ),
        (
            "reference/repository.py",
            """
from typing import Annotated
from pythonarchtesting.rules import subclass_of
from reference.base import BaseRepository

class CsvRepository(BaseRepository):
    __archtest__: Annotated[None, subclass_of("BaseRepository")]
""",
        ),
    ]
    target_modules = [
        (
            "expected/base.py",
            """
class AssignmentRepositoryBase:
    pass
""",
        ),
        (
            "other/base.py",
            """
class BaseRepository:
    pass
""",
        ),
        (
            "student/repository.py",
            """
from other.base import BaseRepository

class CsvRepository(BaseRepository):
    pass
""",
        ),
    ]

    source_entities = [
        entity
        for path, text in source_modules
        for entity in _extract_entities(text, role="source", path=path)
    ]
    target_entities = [
        entity
        for path, text in target_modules
        for entity in _extract_entities(text, role="target", path=path)
    ]
    source_class = _entity(
        source_entities,
        kind="class",
        module_path="reference.repository",
        name="CsvRepository",
    )
    source_base = _entity(
        source_entities,
        kind="class",
        module_path="reference.base",
        name="BaseRepository",
    )
    target_class = _entity(
        target_entities,
        kind="class",
        module_path="student.repository",
        name="CsvRepository",
    )
    matched_target_base = _entity(
        target_entities,
        kind="class",
        module_path="expected.base",
        name="AssignmentRepositoryBase",
    )

    results, errors = _evaluate(
        source_modules=source_modules,
        target_modules=target_modules,
        source_module_path="reference.repository",
        matches=[
            _matched(source_class, target_class),
            _matched(source_base, matched_target_base),
        ],
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "matched counterpart" in results[0].message
