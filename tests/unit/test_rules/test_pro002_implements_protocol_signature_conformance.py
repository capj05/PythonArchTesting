from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_pro002_evaluation_fails_for_protocol_mismatch() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    def get(self, item_id: str) -> str:
        ...

def process(repo: Annotated[object, implements_protocol(Repository)]) -> None:
    return None
"""
    target = """
class BadRepository:
    pass

def process(repo: BadRepository) -> None:
    return None
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="process",
        target_kind="function",
        target_name="process",
        rule_id="PRO002/implements_protocol_signature/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "protocol_mismatch"


def test_pro002_evaluation_fails_for_missing_inherited_protocol_method() -> None:
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


def process(repo: Annotated[object, implements_protocol(Repository)]) -> None:
    return None
"""
    target = """
class SqlRepository:
    def save(self, item_id: str) -> None:
        return None


def process(repo: SqlRepository) -> None:
    return None
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="process",
        target_kind="function",
        target_name="process",
        rule_id="PRO002/implements_protocol_signature/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "protocol_mismatch"
    assert "missing protocol methods: get" in results[0].message


def test_pro002_evaluation_passes_for_parameter_annotation_with_inherited_target_method() -> (
    None
):
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class BaseRepository(Protocol):
    def get(self, item_id: str) -> str:
        ...


class Repository(BaseRepository):
    pass


def process(repo: Annotated[object, implements_protocol(Repository)]) -> None:
    return None
"""
    target = """
class BaseSqlRepository:
    def get(self, item_id: str) -> str:
        return item_id


class SqlRepository(BaseSqlRepository):
    pass


def process(repo: SqlRepository) -> None:
    return None
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="process",
        target_kind="function",
        target_name="process",
        rule_id="PRO002/implements_protocol_signature/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_pro002_evaluation_passes_for_return_annotation_with_composed_protocol() -> (
    None
):
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Reader(Protocol):
    def get(self, item_id: str) -> str:
        ...


class Named(Protocol):
    @property
    def name(self) -> str:
        ...


class Repository(Reader, Named):
    pass


def build() -> Annotated[object, implements_protocol(Repository)]:
    raise NotImplementedError
"""
    target = """
class BaseSqlRepository:
    def get(self, item_id: str) -> str:
        return item_id


class SqlRepository(BaseSqlRepository):
    @property
    def name(self) -> str:
        return "repo"


def build() -> SqlRepository:
    return SqlRepository()
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="build",
        target_kind="function",
        target_name="build",
        subject_kind="return",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_pro002_evaluation_passes_for_parameter_attribute_protocol() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    endpoint: str

def process(repo: Annotated[object, implements_protocol(Repository)]) -> None:
    return None
"""
    target = """
class SqlRepository:
    endpoint: str = "db"

def process(repo: SqlRepository) -> None:
    return None
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="process",
        target_kind="function",
        target_name="process",
        rule_id="PRO002/implements_protocol_signature/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["required_attributes"] == ["endpoint"]


def test_pro002_evaluation_passes_for_return_property_protocol() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Service(Protocol):
    @property
    def status(self) -> str:
        ...

def build() -> Annotated[object, implements_protocol(Service)]:
    raise NotImplementedError
"""
    target = """
class SqlService:
    @property
    def status(self) -> str:
        return "ready"

def build() -> SqlService:
    return SqlService()
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="build",
        target_kind="function",
        target_name="build",
        subject_kind="return",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_pro002_evaluation_fails_for_attribute_protocol_mismatch() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    endpoint: str

def process(repo: Annotated[object, implements_protocol(Repository)]) -> None:
    return None
"""
    target = """
class BadRepository:
    pass

def process(repo: BadRepository) -> None:
    return None
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="process",
        target_kind="function",
        target_name="process",
        rule_id="PRO002/implements_protocol_signature/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "protocol_mismatch"
    assert results[0].details["missing_attributes"] == ["endpoint"]


def test_pro002_parameter_role_rejects_read_only_property_for_writable_attribute_protocol() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    endpoint: str

def process(repo: Annotated[object, implements_protocol(Repository)]) -> None:
    return None
"""
    target = """
class SqlRepository:
    @property
    def endpoint(self) -> str:
        return "db"

def process(repo: SqlRepository) -> None:
    return None
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="process",
        target_kind="function",
        target_name="process",
        rule_id="PRO002/implements_protocol_signature/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "protocol_mismatch"
    assert results[0].details["attribute_errors"] == [
        {
            "attribute": "endpoint",
            "errors": ["attribute mutability mismatch: protocol requires writable member"],
        }
    ]


def test_pro002_return_role_accepts_covariant_read_only_property_protocol() -> None:
    source = """
from typing import Annotated, Protocol
from src.rules import implements_protocol

class BaseStatus:
    pass

class ChildStatus(BaseStatus):
    pass

class Service(Protocol):
    @property
    def status(self) -> BaseStatus:
        ...

def build() -> Annotated[object, implements_protocol(Service)]:
    raise NotImplementedError
"""
    target = """
class BaseStatus:
    pass

class ChildStatus(BaseStatus):
    pass

class SqlService:
    @property
    def status(self) -> ChildStatus:
        return ChildStatus()

def build() -> SqlService:
    return SqlService()
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="build",
        target_kind="function",
        target_name="build",
        subject_kind="return",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_pro002_return_role_accepts_plain_attribute_for_read_only_property_protocol() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Service(Protocol):
    @property
    def status(self) -> str:
        ...

def build() -> Annotated[object, implements_protocol(Service)]:
    raise NotImplementedError
"""
    target = """
class SqlService:
    status: str = "ready"

def build() -> SqlService:
    return SqlService()
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="build",
        target_kind="function",
        target_name="build",
        subject_kind="return",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_pro002_return_role_rejects_read_only_property_for_writable_property_protocol() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Service(Protocol):
    @property
    def status(self) -> str:
        ...

    @status.setter
    def status(self, value: str) -> None:
        ...

def build() -> Annotated[object, implements_protocol(Service)]:
    raise NotImplementedError
"""
    target = """
class SqlService:
    @property
    def status(self) -> str:
        return "ready"

def build() -> SqlService:
    return SqlService()
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="build",
        target_kind="function",
        target_name="build",
        subject_kind="return",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "protocol_mismatch"
    assert results[0].details["attribute_errors"] == [
        {
            "attribute": "status",
            "errors": ["attribute mutability mismatch: protocol requires writable member"],
        }
    ]


def test_pro002_return_role_accepts_writable_property_protocol_through_inherited_target_base() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Service(Protocol):
    @property
    def status(self) -> str:
        ...

    @status.setter
    def status(self, value: str) -> None:
        ...

def build() -> Annotated[object, implements_protocol(Service)]:
    raise NotImplementedError
"""
    target = """
class BaseSqlService:
    @property
    def status(self) -> str:
        return "ready"

    @status.setter
    def status(self, value: str) -> None:
        self._status = value

class SqlService(BaseSqlService):
    pass

def build() -> SqlService:
    return SqlService()
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="build",
        target_kind="function",
        target_name="build",
        subject_kind="return",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_pro002_parameter_role_accepts_contravariant_method_annotation() -> None:
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

def process(repo: Annotated[object, implements_protocol(Repository)]) -> None:
    return None
"""
    target = """
class Animal:
    pass

class Dog(Animal):
    pass

class SqlRepository:
    def save(self, pet: Animal) -> None:
        return None

def process(repo: SqlRepository) -> None:
    return None
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="process",
        target_kind="function",
        target_name="process",
        rule_id="PRO002/implements_protocol_signature/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_pro002_return_role_accepts_covariant_method_annotation() -> None:
    source = """
from typing import Annotated, Protocol
from src.rules import implements_protocol

class BaseResult:
    pass

class Service(Protocol):
    def build(self) -> BaseResult:
        ...

def build() -> Annotated[
    object,
    implements_protocol(Service, return_annotation="error"),
]:
    raise NotImplementedError
"""
    target = """
class BaseResult:
    pass

class ChildResult(BaseResult):
    pass

class SqlService:
    def build(self) -> ChildResult:
        return ChildResult()

def build() -> SqlService:
    return SqlService()
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="build",
        target_kind="function",
        target_name="build",
        subject_kind="return",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
