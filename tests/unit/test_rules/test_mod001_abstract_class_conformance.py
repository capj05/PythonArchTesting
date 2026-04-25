from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_mod001_declared_abstract_method_makes_class_abstract() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_abstract_class

class Contract:
    __archtest__: Annotated[None, is_abstract_class()]
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
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="MOD001/is_abstract_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["unresolved_abstract_names"] == ["render"]


def test_mod001_declared_abstract_method_fails_concrete_class_rule() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_concrete_class

class Contract:
    __archtest__: Annotated[None, is_concrete_class()]
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
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="MOD001/is_concrete_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["unresolved_abstract_names"] == ["render"]


def test_mod001_concrete_override_satisfies_inherited_abstract_method() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_concrete_class

class Contract:
    __archtest__: Annotated[None, is_concrete_class()]
"""
    target = """
from abc import abstractmethod

class Base:
    @abstractmethod
    def render(self) -> str:
        raise NotImplementedError


class Contract(Base):
    def render(self) -> str:
        return "ok"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="MOD001/is_concrete_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["unresolved_abstract_names"] == []


def test_mod001_inherited_unresolved_abstract_method_keeps_class_abstract() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_abstract_class

class Contract:
    __archtest__: Annotated[None, is_abstract_class()]
"""
    target = """
from abc import abstractmethod

class Base:
    @abstractmethod
    def render(self) -> str:
        raise NotImplementedError


class Contract(Base):
    pass
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="MOD001/is_abstract_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["unresolved_abstract_names"] == ["render"]
    assert results[0].details["local_base_classes"] == ["target_module.Base"]


def test_mod001_plain_class_is_concrete() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_concrete_class

class Contract:
    __archtest__: Annotated[None, is_concrete_class()]
"""
    target = """
class Contract:
    def render(self) -> str:
        return "ok"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="MOD001/is_concrete_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["unresolved_abstract_names"] == []


def test_mod001_recursive_local_abstract_obligations_propagate() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_abstract_class

class Contract:
    __archtest__: Annotated[None, is_abstract_class()]
"""
    target = """
from abc import abstractmethod

class Root:
    @abstractmethod
    def render(self) -> str:
        raise NotImplementedError


class Intermediate(Root):
    pass


class Contract(Intermediate):
    pass
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="MOD001/is_abstract_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["unresolved_abstract_names"] == ["render"]
    assert results[0].details["local_base_classes"] == ["target_module.Intermediate"]


def test_mod001_external_abstract_bases_are_not_over_claimed() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_concrete_class

class Contract:
    __archtest__: Annotated[None, is_concrete_class()]
"""
    target = """
from collections.abc import Iterable

class Contract(Iterable):
    pass
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="MOD001/is_concrete_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["local_base_classes"] == []
    assert results[0].details["unresolved_abstract_names"] == []
