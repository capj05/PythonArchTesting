from __future__ import annotations

from src.protocols.introspection import class_methods
from tests.unit.test_rules.protocol_rule_test_helpers import (
    evaluate_single_rule,
    extract_entities,
)


def test_pro001_evaluation_passes_for_compatible_protocol() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    def get(self, item_id: str) -> str:
        ...

    @classmethod
    def from_url(cls, url: str) -> "Repository":
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class SqlRepository:
    def get(self, item_id: str) -> str:
        return item_id

    @classmethod
    def from_url(cls, url: str) -> "SqlRepository":
        return cls()
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="SqlRepository",
        target_kind="class",
        target_name="SqlRepository",
        rule_id="PRO001/implements_protocol/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_pro001_evaluation_fails_for_missing_protocol_method() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    def get(self, item_id: str) -> str:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class SqlRepository:
    pass
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="SqlRepository",
        target_kind="class",
        target_name="SqlRepository",
        rule_id="PRO001/implements_protocol/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "missing protocol methods" in results[0].message


def test_pro001_evaluation_fails_for_method_signature_mismatch() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    @classmethod
    def get(cls, item_id: str) -> str:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class SqlRepository:
    def get(self, item_id: int) -> str:
        return str(item_id)
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="SqlRepository",
        target_kind="class",
        target_name="SqlRepository",
        rule_id="PRO001/implements_protocol/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "method kind mismatch" in results[0].message


def test_pro001_evaluation_fails_for_missing_inherited_protocol_method() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class BaseRepository(Protocol):
    def get(self, item_id: str) -> str:
        ...


class Repository(BaseRepository):
    def save(self, item_id: str) -> None:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol(Repository)]
"""
    target = """
class SqlRepository:
    def save(self, item_id: str) -> None:
        return None
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="SqlRepository",
        target_kind="class",
        target_name="SqlRepository",
        rule_id="PRO001/implements_protocol/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "missing protocol methods: get" in results[0].message


def test_pro001_evaluation_passes_for_method_inherited_from_target_base_class() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class BaseRepository(Protocol):
    def get(self, item_id: str) -> str:
        ...


class Repository(BaseRepository):
    pass


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol(Repository)]
"""
    target = """
class BaseSqlRepository:
    def get(self, item_id: str) -> str:
        return item_id


class SqlRepository(BaseSqlRepository):
    pass
"""
    target_entities = extract_entities(target, role="target")
    target_entity = next(
        entity
        for entity in target_entities
        if entity.kind == "class" and entity.name == "SqlRepository"
    )

    assert [method.name for method in class_methods(target_entity, target_entities)] == [
        "get"
    ]

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="SqlRepository",
        target_kind="class",
        target_name="SqlRepository",
        rule_id="PRO001/implements_protocol/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_pro001_evaluation_accepts_contravariant_parameter_annotation() -> None:
    source = """
from typing import Annotated, Protocol
from src.rules import implements_protocol

class Animal:
    pass

class Dog(Animal):
    pass

class Repository(Protocol):
    def save(self, pet: Dog) -> None:
        ...

class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class Animal:
    pass

class Dog(Animal):
    pass

class SqlRepository:
    def save(self, pet: Animal) -> None:
        return None
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="SqlRepository",
        target_kind="class",
        target_name="SqlRepository",
        rule_id="PRO001/implements_protocol/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_pro001_evaluation_rejects_narrower_parameter_annotation() -> None:
    source = """
from typing import Annotated, Protocol
from src.rules import implements_protocol

class Animal:
    pass

class Dog(Animal):
    pass

class Repository(Protocol):
    def save(self, pet: Animal) -> None:
        ...

class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class Animal:
    pass

class Dog(Animal):
    pass

class SqlRepository:
    def save(self, pet: Dog) -> None:
        return None
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="SqlRepository",
        target_kind="class",
        target_name="SqlRepository",
        rule_id="PRO001/implements_protocol/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "parameter annotation mismatch" in results[0].message


def test_pro001_evaluation_accepts_covariant_return_annotation() -> None:
    source = """
from typing import Annotated, Protocol
from src.rules import implements_protocol

class BaseResult:
    pass

class Repository(Protocol):
    def build(self) -> BaseResult:
        ...

class SqlRepository:
    __archtest__: Annotated[
        None,
        implements_protocol("source_module.Repository", return_annotation="error"),
    ]
"""
    target = """
class BaseResult:
    pass

class ChildResult(BaseResult):
    pass

class SqlRepository:
    def build(self) -> ChildResult:
        return ChildResult()
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="SqlRepository",
        target_kind="class",
        target_name="SqlRepository",
        rule_id="PRO001/implements_protocol/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
