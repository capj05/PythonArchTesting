from __future__ import annotations

from pythonarchtesting.matching import MatchStatus
from tests.unit.test_rules._nom001_helpers import (
    entity,
    evaluate_nom001_rule,
    extract_modules,
    match_with_status,
    matched,
)


def test_nom001_not_subclass_of_evaluation_passes_for_unrelated_target() -> None:
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import not_subclass_of

class BaseRepository:
    pass


class CsvRepository:
    __archtest__: Annotated[None, not_subclass_of("source_module.BaseRepository")]
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

    source_entities = extract_modules(source_modules, role="source")
    target_entities = extract_modules(target_modules, role="target")
    source_class = entity(
        source_entities, kind="class", module_path="source_module", name="CsvRepository"
    )
    source_base = entity(
        source_entities,
        kind="class",
        module_path="source_module",
        name="BaseRepository",
    )
    target_class = entity(
        target_entities, kind="class", module_path="target_module", name="CsvRepository"
    )
    target_base = entity(
        target_entities,
        kind="class",
        module_path="target_module",
        name="AssignmentRepositoryBase",
    )

    results, errors = evaluate_nom001_rule(
        rule_id="NOM001/not_subclass_of/v1",
        source_modules=source_modules,
        target_modules=target_modules,
        source_module_path="source_module",
        matches=[
            matched(source_class, target_class),
            matched(source_base, target_base),
        ],
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_nom001_not_subclass_of_evaluation_fails_for_direct_subclass() -> None:
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import not_subclass_of

class BaseRepository:
    pass


class CsvRepository:
    __archtest__: Annotated[None, not_subclass_of("source_module.BaseRepository")]
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

    source_entities = extract_modules(source_modules, role="source")
    target_entities = extract_modules(target_modules, role="target")
    source_class = entity(
        source_entities, kind="class", module_path="source_module", name="CsvRepository"
    )
    source_base = entity(
        source_entities,
        kind="class",
        module_path="source_module",
        name="BaseRepository",
    )
    target_class = entity(
        target_entities, kind="class", module_path="target_module", name="CsvRepository"
    )
    target_base = entity(
        target_entities,
        kind="class",
        module_path="target_module",
        name="AssignmentRepositoryBase",
    )

    results, errors = evaluate_nom001_rule(
        rule_id="NOM001/not_subclass_of/v1",
        source_modules=source_modules,
        target_modules=target_modules,
        source_module_path="source_module",
        matches=[
            matched(source_class, target_class),
            matched(source_base, target_base),
        ],
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "forbidden base" in results[0].message


def test_nom001_not_subclass_of_evaluation_fails_for_transitive_subclass() -> None:
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import not_subclass_of

class BaseRepository:
    pass


class CsvRepository:
    __archtest__: Annotated[None, not_subclass_of("source_module.BaseRepository")]
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

    source_entities = extract_modules(source_modules, role="source")
    target_entities = extract_modules(target_modules, role="target")
    source_class = entity(
        source_entities, kind="class", module_path="source_module", name="CsvRepository"
    )
    source_base = entity(
        source_entities,
        kind="class",
        module_path="source_module",
        name="BaseRepository",
    )
    target_class = entity(
        target_entities, kind="class", module_path="target_module", name="CsvRepository"
    )
    target_base = entity(
        target_entities,
        kind="class",
        module_path="target_module",
        name="AssignmentRepositoryBase",
    )

    results, errors = evaluate_nom001_rule(
        rule_id="NOM001/not_subclass_of/v1",
        source_modules=source_modules,
        target_modules=target_modules,
        source_module_path="source_module",
        matches=[
            matched(source_class, target_class),
            matched(source_base, target_base),
        ],
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "forbidden base" in results[0].message


def test_nom001_not_subclass_of_evaluation_fails_for_exact_forbidden_base() -> None:
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import not_subclass_of

class BaseRepository:
    pass


class CsvRepository:
    __archtest__: Annotated[None, not_subclass_of("source_module.BaseRepository")]
""",
        )
    ]
    target_modules = [
        (
            "target_module.py",
            """
class AssignmentRepositoryBase:
    pass
""",
        )
    ]

    source_entities = extract_modules(source_modules, role="source")
    target_entities = extract_modules(target_modules, role="target")
    source_class = entity(
        source_entities, kind="class", module_path="source_module", name="CsvRepository"
    )
    source_base = entity(
        source_entities,
        kind="class",
        module_path="source_module",
        name="BaseRepository",
    )
    target_base = entity(
        target_entities,
        kind="class",
        module_path="target_module",
        name="AssignmentRepositoryBase",
    )

    results, errors = evaluate_nom001_rule(
        rule_id="NOM001/not_subclass_of/v1",
        source_modules=source_modules,
        target_modules=target_modules,
        source_module_path="source_module",
        matches=[
            matched(source_class, target_base),
            matched(source_base, target_base),
        ],
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "forbidden base counterpart" in results[0].message


def test_nom001_not_subclass_of_evaluation_fails_when_expected_base_counterpart_is_unmatched() -> (
    None
):
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import not_subclass_of

class BaseRepository:
    pass


class CsvRepository:
    __archtest__: Annotated[None, not_subclass_of("source_module.BaseRepository")]
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

    source_entities = extract_modules(source_modules, role="source")
    target_entities = extract_modules(target_modules, role="target")
    source_class = entity(
        source_entities, kind="class", module_path="source_module", name="CsvRepository"
    )
    source_base = entity(
        source_entities,
        kind="class",
        module_path="source_module",
        name="BaseRepository",
    )
    target_class = entity(
        target_entities, kind="class", module_path="target_module", name="CsvRepository"
    )

    results, errors = evaluate_nom001_rule(
        rule_id="NOM001/not_subclass_of/v1",
        source_modules=source_modules,
        target_modules=target_modules,
        source_module_path="source_module",
        matches=[
            matched(source_class, target_class),
            match_with_status(source_base, MatchStatus.UNMATCHED),
        ],
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "required base counterpart is not available" in results[0].message
