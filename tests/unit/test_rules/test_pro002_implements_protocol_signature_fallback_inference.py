from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_pro002_evaluation_passes_for_unannotated_return_direct_constructor() -> None:
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

def build():
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
    assert results[0].details["resolution_source"] == "local_ast_fallback"
    assert results[0].details["inference_kind"] == "return_direct_constructor"
    assert results[0].details["inferred_target_reference"] == "SqlService"


def test_pro002_evaluation_passes_for_unannotated_return_assigned_constructor() -> None:
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

def build():
    service = SqlService()
    return service
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
    assert results[0].details["resolution_source"] == "local_ast_fallback"
    assert results[0].details["inference_kind"] == "return_assigned_local_constructor"
    assert results[0].details["inferred_target_reference"] == "SqlService"


def test_pro002_evaluation_passes_for_unannotated_parameter_default_constructor() -> (
    None
):
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

def process(repo=SqlRepository()) -> None:
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
    assert results[0].details["resolution_source"] == "local_ast_fallback"
    assert results[0].details["inference_kind"] == "param_default_constructor"
    assert results[0].details["inferred_target_reference"] == "SqlRepository"


def test_pro002_evaluation_fails_for_unannotated_return_conflicting_local_classes() -> (
    None
):
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

class AltService:
    def run(self, payload: str) -> str:
        return payload

def build(flag: bool):
    if flag:
        return SqlService()
    return AltService()
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
    assert results[0].details["resolution_source"] == "local_ast_fallback"
    assert (
        results[0].details["inference_kind"] == "return_conflicting_local_constructors"
    )
    assert results[0].details["failure_reason"] == "ambiguous_or_missing"


def test_pro002_evaluation_passes_for_return_same_module_helper_direct_constructor() -> (
    None
):
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

def make_service():
    return SqlService()

def build():
    return make_service()
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
    assert results[0].details["resolution_source"] == "local_ast_fallback"
    assert (
        results[0].details["inference_kind"] == "return_same_module_helper_constructor"
    )
    assert results[0].details["inferred_target_reference"] == "SqlService"


def test_pro002_evaluation_passes_for_return_same_module_helper_assigned_constructor() -> (
    None
):
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

def make_service():
    service = SqlService()
    return service

def build():
    return make_service()
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
    assert results[0].details["resolution_source"] == "local_ast_fallback"
    assert (
        results[0].details["inference_kind"] == "return_same_module_helper_constructor"
    )
    assert results[0].details["inferred_target_reference"] == "SqlService"


def test_pro002_evaluation_fails_for_return_same_module_helper_conflicting_classes() -> (
    None
):
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

class AltService:
    def run(self, payload: str) -> str:
        return payload

def make_service(flag: bool):
    if flag:
        return SqlService()
    return AltService()

def build():
    return make_service(True)
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
    assert results[0].details["resolution_source"] == "local_ast_fallback"
    assert (
        results[0].details["inference_kind"] == "return_conflicting_local_constructors"
    )
    assert results[0].details["failure_reason"] == "ambiguous_or_missing"


def test_pro002_fails_for_return_same_module_helper_nested_helper_call() -> None:
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

def inner_service():
    return SqlService()

def make_service():
    return inner_service()

def build():
    return make_service()
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
    assert results[0].details["failure_reason"] == "missing_target_annotation"


def test_pro002_evaluation_fails_for_unannotated_return_helper_attribute_call() -> None:
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

class Factory:
    def make_service(self):
        return SqlService()

factory = Factory()

def build():
    return factory.make_service()
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
    assert results[0].details["failure_reason"] == "missing_target_annotation"


def test_pro002_evaluation_fails_for_unannotated_return_same_module_helper_cycle() -> (
    None
):
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
def build():
    return make_service()

def make_service():
    return build()
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
    assert results[0].details["resolution_source"] == "local_ast_fallback"
    assert results[0].details["inference_kind"] == "return_same_module_helper_cycle"
    assert results[0].details["failure_reason"] == "ambiguous_or_missing"
