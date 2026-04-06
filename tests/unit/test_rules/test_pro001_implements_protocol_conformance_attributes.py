from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_pro001_evaluation_passes_for_property_protocol_member() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    @property
    def name(self) -> str:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class SqlRepository:
    @property
    def name(self) -> str:
        return "ok"
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
    assert results[0].details["required_attributes"] == ["name"]


def test_pro001_evaluation_passes_for_annotated_attribute_protocol_member() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    name: str


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class SqlRepository:
    name: str = "db"
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


def test_pro001_evaluation_passes_for_constant_protocol_member() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    DEFAULT_LIMIT = 100


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class SqlRepository:
    DEFAULT_LIMIT = 10
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


def test_pro001_evaluation_fails_for_missing_attribute_protocol_member() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    name: str


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
    assert results[0].details["missing_attributes"] == ["name"]


def test_pro001_evaluation_fails_for_attribute_annotation_mismatch() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    name: str


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class SqlRepository:
    name: int = 1
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
    assert results[0].details["attribute_errors"] == [
        {
            "attribute": "name",
            "errors": ["attribute annotation mismatch: expected str, found int"],
        }
    ]


def test_pro001_evaluation_fails_for_missing_attribute_annotation() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    name: str


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class SqlRepository:
    name = "db"
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
    assert results[0].details["attribute_errors"] == [
        {
            "attribute": "name",
            "errors": ["attribute annotation mismatch: expected str, found None"],
        }
    ]


def test_pro001_evaluation_does_not_treat_method_as_attribute_match() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    name: str


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class SqlRepository:
    def name(self) -> str:
        return "db"
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
    assert results[0].details["missing_attributes"] == ["name"]


def test_pro001_evaluation_rejects_read_only_property_for_writable_attribute_protocol() -> (
    None
):
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    name: str


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class SqlRepository:
    @property
    def name(self) -> str:
        return "db"
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
    assert results[0].details["attribute_errors"] == [
        {
            "attribute": "name",
            "errors": [
                "attribute mutability mismatch: protocol requires writable member"
            ],
        }
    ]


def test_pro001_evaluation_accepts_covariant_read_only_property_protocol() -> None:
    source = """
from typing import Annotated, Protocol
from src.rules import implements_protocol

class BaseName:
    pass

class ChildName(BaseName):
    pass

class Repository(Protocol):
    @property
    def name(self) -> BaseName:
        ...

class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class BaseName:
    pass

class ChildName(BaseName):
    pass

class SqlRepository:
    @property
    def name(self) -> ChildName:
        return ChildName()
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


def test_pro001_evaluation_accepts_plain_attribute_for_read_only_property_protocol() -> (
    None
):
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    @property
    def name(self) -> str:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class SqlRepository:
    name: str = "db"
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


def test_pro001_evaluation_rejects_read_only_property_for_writable_property_protocol() -> (
    None
):
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    @property
    def name(self) -> str:
        ...

    @name.setter
    def name(self, value: str) -> None:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class SqlRepository:
    @property
    def name(self) -> str:
        return "db"
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
    assert results[0].details["attribute_errors"] == [
        {
            "attribute": "name",
            "errors": [
                "attribute mutability mismatch: protocol requires writable member"
            ],
        }
    ]


def test_pro001_evaluation_accepts_writable_property_protocol_through_inherited_target_base() -> (
    None
):
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    @property
    def name(self) -> str:
        ...

    @name.setter
    def name(self, value: str) -> None:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class BaseSqlRepository:
    @property
    def name(self) -> str:
        return "db"

    @name.setter
    def name(self, value: str) -> None:
        self._name = value


class SqlRepository(BaseSqlRepository):
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
    assert [result.status for result in results] == ["OK"]


def test_pro001_evaluation_accepts_normalized_attribute_annotation() -> None:
    source = """
from typing import Annotated, Optional, Protocol
from src.rules import implements_protocol

class Name:
    pass

class Repository(Protocol):
    label: Optional[Name]

class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class Name:
    pass

class SqlRepository:
    label: Name | None = None
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


def test_pro001_evaluation_accepts_plain_attribute_for_deferred_classvar_protocol() -> (
    None
):
    source = """
from typing import Annotated, ClassVar, Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    flag: ClassVar[bool]

class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class SqlRepository:
    flag: bool = True
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


def test_pro001_evaluation_accepts_classvar_attribute_for_deferred_classvar_protocol() -> (
    None
):
    source = """
from typing import Annotated, ClassVar, Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    flag: ClassVar[bool]

class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
from typing import ClassVar

class SqlRepository:
    flag: ClassVar[bool] = True
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


def test_pro001_evaluation_rejects_mismatched_inner_type_for_deferred_classvar_protocol() -> (
    None
):
    source = """
from typing import Annotated, ClassVar, Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    flag: ClassVar[bool]

class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    target = """
class SqlRepository:
    flag: int = 1
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
    assert results[0].details["attribute_errors"] == [
        {
            "attribute": "flag",
            "errors": ["attribute annotation mismatch: expected bool, found int"],
        }
    ]
