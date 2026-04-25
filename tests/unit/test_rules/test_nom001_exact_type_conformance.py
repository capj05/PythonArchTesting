from __future__ import annotations

from pythonarchtesting.matching import MatchStatus
from tests.unit.test_rules._nom001_helpers import (
    entity,
    evaluate_nom001_rule,
    extract_modules,
    match_with_status,
    matched,
)


def test_nom001_exact_type_evaluation_passes_for_exact_match() -> None:
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import exact_type

class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[None, exact_type("source_module.BaseRepository")]
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
        rule_id="NOM001/exact_type/v1",
        source_modules=source_modules,
        target_modules=target_modules,
        source_module_path="source_module",
        matches=[
            matched(source_class, target_base),
            matched(source_base, target_base),
        ],
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_nom001_exact_type_evaluation_fails_for_subclass() -> None:
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import exact_type

class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[None, exact_type("source_module.BaseRepository")]
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
        rule_id="NOM001/exact_type/v1",
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
    assert "not exactly the matched counterpart" in results[0].message


def test_nom001_exact_type_evaluation_fails_for_unrelated_target() -> None:
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import exact_type

class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[None, exact_type("source_module.BaseRepository")]
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
        rule_id="NOM001/exact_type/v1",
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
    assert "not exactly the matched counterpart" in results[0].message


def test_nom001_exact_type_evaluation_fails_when_expected_base_counterpart_is_unmatched() -> (
    None
):
    source_modules = [
        (
            "source_module.py",
            """
from typing import Annotated
from pythonarchtesting.rules import exact_type

class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[None, exact_type("source_module.BaseRepository")]
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
        rule_id="NOM001/exact_type/v1",
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
