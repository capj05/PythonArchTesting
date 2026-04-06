from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_pro002_evaluation_passes_for_parameter_annotation() -> None:
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
class SqlRepository:
    def get(self, item_id: str) -> str:
        return item_id

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


def test_pro002_evaluation_passes_for_return_annotation() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Service(Protocol):
    def run(self, payload: str) -> str:
        ...

def build() -> Annotated[object, implements_protocol(Service)]:
    raise NotImplementedError
"""
    target = """
class SqlService:
    def run(self, payload: str) -> str:
        return payload

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


def test_pro002_evaluation_fails_for_missing_target_annotation() -> None:
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
class SqlRepository:
    def get(self, item_id: str) -> str:
        return item_id

def process(repo) -> None:
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
    assert results[0].details["failure_reason"] == "missing_target_annotation"


def test_pro002_evaluation_fails_for_unresolved_target_annotation() -> None:
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
def process(repo: MissingRepository) -> None:
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
    assert results[0].details["failure_reason"] == "ambiguous_or_missing"


def test_pro002_evaluation_passes_for_wrapped_target_annotation_with_alias() -> None:
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
from typing import Annotated
from target_module import SqlRepository as RepoImpl

class SqlRepository:
    def get(self, item_id: str) -> str:
        return item_id

def process(repo: Annotated[RepoImpl | None, "target-role"]) -> None:
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
    assert (
        results[0].details["resolved_target_annotation"]
        == "target_module.SqlRepository"
    )


def test_pro002_evaluation_passes_for_container_parameter_annotation() -> None:
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
class SqlRepository:
    def get(self, item_id: str) -> str:
        return item_id

def process(repo: list[SqlRepository]) -> None:
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
    assert (
        results[0].details["resolved_target_annotation"]
        == "target_module.SqlRepository"
    )


def test_pro002_evaluation_passes_for_container_return_annotation() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Service(Protocol):
    def run(self, payload: str) -> str:
        ...

def build() -> Annotated[object, implements_protocol(Service)]:
    raise NotImplementedError
"""
    target = """
from typing import Sequence

class SqlService:
    def run(self, payload: str) -> str:
        return payload

def build() -> Sequence[SqlService]:
    return [SqlService()]
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
    assert (
        results[0].details["resolved_target_annotation"] == "target_module.SqlService"
    )


def test_pro002_evaluation_rejects_multi_class_container_target_annotation() -> None:
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
class SqlRepository:
    def get(self, item_id: str) -> str:
        return item_id

class AltRepository:
    def get(self, item_id: str) -> str:
        return item_id

def process(repo: dict[str, SqlRepository | AltRepository]) -> None:
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
    assert results[0].details["failure_reason"] == "ambiguous_or_missing"


def test_pro002_evaluation_resolves_import_aliases_and_method_receiver_slots() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    def get(self, item_id: str) -> str:
        ...

class Service:
    def process(self, repo: Annotated[object, implements_protocol(Repository)]) -> None:
        return None
"""
    target = """
from target_module import SqlRepository as RepoImpl

class SqlRepository:
    def get(self, item_id: str) -> str:
        return item_id

class Service:
    def process(self, repo: RepoImpl) -> None:
        return None
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="process",
        target_kind="method",
        target_name="process",
        rule_id="PRO002/implements_protocol_signature/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_pro002_evaluation_uses_canonical_slots_for_vararg_and_kwonly_annotations() -> (
    None
):
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class ItemsRepository(Protocol):
    def collect(self, item_id: str) -> str:
        ...


class FlagService(Protocol):
    def run(self, enabled: bool) -> bool:
        ...


def process(
    self,
    first: int,
    *items: Annotated[object, implements_protocol(ItemsRepository)],
    flag: Annotated[object, implements_protocol(FlagService)],
    **metadata: bytes,
) -> None:
    return None
"""
    target = """
class SqlItemsRepository:
    def collect(self, item_id: str) -> str:
        return item_id


class SqlFlagService:
    def run(self, enabled: bool) -> bool:
        return enabled


def process(
    self,
    first: int,
    *items: SqlItemsRepository,
    flag: SqlFlagService,
    **metadata: bytes,
) -> None:
    return None
"""
    vararg_results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="process",
        target_kind="function",
        target_name="process",
        rule_id="PRO002/implements_protocol_signature/v1/d0",
    )
    kwonly_results, kwonly_errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="function",
        source_name="process",
        target_kind="function",
        target_name="process",
        rule_id="PRO002/implements_protocol_signature/v1/d1",
    )

    assert errors == []
    assert kwonly_errors == []
    assert [result.status for result in vararg_results] == ["OK"]
    assert [result.status for result in kwonly_results] == ["OK"]
    assert vararg_results[0].details["subject_index"] == 1
    assert kwonly_results[0].details["subject_index"] == 2
