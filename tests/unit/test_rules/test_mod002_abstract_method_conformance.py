from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_mod002_abstract_method_passes_for_direct_abstractmethod_import() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_abstract_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_abstract_method()]
        raise NotImplementedError
"""
    target = """
from abc import abstractmethod

class Contract:
    @abstractmethod
    def render(self) -> str:
        raise NotImplementedError
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="render",
        target_kind="method",
        target_name="render",
        rule_id="MOD002/is_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["recognized_abstract_decorator"] == "abc.abstractmethod"


def test_mod002_abstract_method_passes_for_qualified_abc_decorator() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_abstract_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_abstract_method()]
        raise NotImplementedError
"""
    target = """
import abc

class Contract:
    @abc.abstractmethod
    def render(self) -> str:
        raise NotImplementedError
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="render",
        target_kind="method",
        target_name="render",
        rule_id="MOD002/is_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["recognized_abstract_decorator"] == "abc.abstractmethod"


def test_mod002_abstract_method_passes_for_aliased_abstractmethod_import() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_abstract_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_abstract_method()]
        raise NotImplementedError
"""
    target = """
from abc import abstractmethod as abstract

class Contract:
    @abstract
    def render(self) -> str:
        raise NotImplementedError
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="render",
        target_kind="method",
        target_name="render",
        rule_id="MOD002/is_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["recognized_abstract_decorator"] == "abc.abstractmethod"


def test_mod002_abstract_method_passes_for_abstract_classmethod() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_abstract_method

class Contract:
    @classmethod
    def create(cls) -> "Contract":
        __archtest__: Annotated[None, is_abstract_method()]
        raise NotImplementedError
"""
    target = """
from abc import abstractmethod

class Contract:
    @classmethod
    @abstractmethod
    def create(cls) -> "Contract":
        raise NotImplementedError
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="create",
        target_kind="method",
        target_name="create",
        rule_id="MOD002/is_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert "abc.abstractmethod" in results[0].details["normalized_decorators"]


def test_mod002_abstract_method_passes_for_abstract_staticmethod() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_abstract_method

class Contract:
    @staticmethod
    def parse(value: str) -> str:
        __archtest__: Annotated[None, is_abstract_method()]
        raise NotImplementedError
"""
    target = """
from abc import abstractmethod

class Contract:
    @staticmethod
    @abstractmethod
    def parse(value: str) -> str:
        raise NotImplementedError
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="parse",
        target_kind="method",
        target_name="parse",
        rule_id="MOD002/is_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_mod002_abstract_method_passes_for_abstract_property() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_abstract_method

class Contract:
    @property
    def name(self) -> str:
        __archtest__: Annotated[None, is_abstract_method()]
        raise NotImplementedError
"""
    target = """
from abc import abstractmethod

class Contract:
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="name",
        target_kind="method",
        target_name="name",
        rule_id="MOD002/is_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["target_method"]["is_property"] is True


def test_mod002_concrete_method_fails_abstract_method_rule() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_abstract_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_abstract_method()]
        raise NotImplementedError
"""
    target = """
class Contract:
    def render(self) -> str:
        return "ok"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="render",
        target_kind="method",
        target_name="render",
        rule_id="MOD002/is_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["recognized_abstract_decorator"] is None
    assert (
        results[0].details["reason"]
        == "target method is not decorated with a recognized abstract decorator"
    )
