from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_mod003_non_abstract_method_passes_for_plain_method() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_abstract_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_non_abstract_method()]
        return ""
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
        rule_id="MOD003/is_non_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["recognized_abstract_decorator"] is None
    assert results[0].details["modifier_polarity"] == "negative"
    assert results[0].details["failure_reason"] == "forbidden_abstract_method_absent"
    assert results[0].details["modifier_kind"] == "non_abstract_method"


def test_mod003_non_abstract_method_passes_for_classmethod() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_abstract_method

class Contract:
    @classmethod
    def create(cls) -> "Contract":
        __archtest__: Annotated[None, is_non_abstract_method()]
        return cls()
"""
    target = """
class Contract:
    @classmethod
    def create(cls) -> "Contract":
        return cls()
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="create",
        target_kind="method",
        target_name="create",
        rule_id="MOD003/is_non_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_mod003_non_abstract_method_passes_for_staticmethod() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_abstract_method

class Contract:
    @staticmethod
    def parse(value: str) -> str:
        __archtest__: Annotated[None, is_non_abstract_method()]
        return value
"""
    target = """
class Contract:
    @staticmethod
    def parse(value: str) -> str:
        return value
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="parse",
        target_kind="method",
        target_name="parse",
        rule_id="MOD003/is_non_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_mod003_non_abstract_method_passes_for_property() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_abstract_method

class Contract:
    @property
    def name(self) -> str:
        __archtest__: Annotated[None, is_non_abstract_method()]
        return "demo"
"""
    target = """
class Contract:
    @property
    def name(self) -> str:
        return "demo"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="name",
        target_kind="method",
        target_name="name",
        rule_id="MOD003/is_non_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_mod003_non_abstract_method_fails_for_abstractmethod() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_abstract_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_non_abstract_method()]
        return ""
"""
    target = """
from abc import abstractmethod

class Contract:
    @abstractmethod
    def render(self) -> str:
        ...
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="render",
        target_kind="method",
        target_name="render",
        rule_id="MOD003/is_non_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["recognized_abstract_decorator"] == "abc.abstractmethod"
    assert results[0].details["modifier_polarity"] == "negative"
    assert results[0].details["failure_reason"] == "forbidden_abstract_method_present"


def test_mod003_non_abstract_method_fails_for_abc_qualified_decorator() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_abstract_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_non_abstract_method()]
        return ""
"""
    target = """
import abc

class Contract:
    @abc.abstractmethod
    def render(self) -> str:
        ...
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="render",
        target_kind="method",
        target_name="render",
        rule_id="MOD003/is_non_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["recognized_abstract_decorator"] == "abc.abstractmethod"
    assert results[0].details["failure_reason"] == "forbidden_abstract_method_present"


def test_mod003_non_abstract_method_fails_for_abstractclassmethod() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_abstract_method

class Contract:
    @classmethod
    def create(cls) -> "Contract":
        __archtest__: Annotated[None, is_non_abstract_method()]
        return cls()
"""
    target = """
from abc import abstractclassmethod

class Contract:
    @abstractclassmethod
    def create(cls) -> "Contract":
        ...
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="create",
        target_kind="method",
        target_name="create",
        rule_id="MOD003/is_non_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "forbidden_abstract_method_present"


def test_mod003_non_abstract_method_fails_for_abstractproperty() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_abstract_method

class Contract:
    @property
    def name(self) -> str:
        __archtest__: Annotated[None, is_non_abstract_method()]
        return ""
"""
    target = """
from abc import abstractproperty

class Contract:
    @abstractproperty
    def name(self) -> str:
        ...
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="name",
        target_kind="method",
        target_name="name",
        rule_id="MOD003/is_non_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "forbidden_abstract_method_present"


def test_mod003_non_abstract_method_fails_for_aliased_abstractmethod() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_abstract_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_non_abstract_method()]
        return ""
"""
    target = """
from abc import abstractmethod as abstract

class Contract:
    @abstract
    def render(self) -> str:
        ...
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="render",
        target_kind="method",
        target_name="render",
        rule_id="MOD003/is_non_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["recognized_abstract_decorator"] == "abc.abstractmethod"
    assert results[0].details["failure_reason"] == "forbidden_abstract_method_present"


def test_mod003_non_abstract_method_fails_for_abstract_classmethod_combo() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_abstract_method

class Contract:
    @classmethod
    def create(cls) -> "Contract":
        __archtest__: Annotated[None, is_non_abstract_method()]
        return cls()
"""
    target = """
from abc import abstractmethod

class Contract:
    @classmethod
    @abstractmethod
    def create(cls) -> "Contract":
        ...
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="create",
        target_kind="method",
        target_name="create",
        rule_id="MOD003/is_non_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "forbidden_abstract_method_present"


def test_mod003_non_abstract_method_fails_for_abstract_property_combo() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_abstract_method

class Contract:
    @property
    def name(self) -> str:
        __archtest__: Annotated[None, is_non_abstract_method()]
        return ""
"""
    target = """
from abc import abstractmethod

class Contract:
    @property
    @abstractmethod
    def name(self) -> str:
        ...
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="method",
        source_name="name",
        target_kind="method",
        target_name="name",
        rule_id="MOD003/is_non_abstract_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "forbidden_abstract_method_present"
