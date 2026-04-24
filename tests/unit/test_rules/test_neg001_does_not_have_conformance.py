from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_neg001_evaluation_passes_when_forbidden_method_is_absent() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[None, does_not_have("debug_dump", member_kind="method")]
"""
    target = """
class User:
    def save(self) -> None:
        return None
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_neg001_evaluation_fails_when_forbidden_method_is_declared() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[None, does_not_have("debug_dump", member_kind="method")]
"""
    target = """
class User:
    def debug_dump(self) -> str:
        return "trace"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "forbidden method 'debug_dump' is present" in results[0].message


def test_neg001_evaluation_fails_for_inherited_method_by_default() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[None, does_not_have("debug_dump", member_kind="method")]
"""
    target = """
class Base:
    def debug_dump(self) -> str:
        return "trace"


class User(Base):
    pass
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "forbidden inherited method 'debug_dump' is present" in results[0].message


def test_neg001_evaluation_passes_for_inherited_method_when_declared_only() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have("debug_dump", member_kind="method", declared_only=True),
    ]
"""
    target = """
class Base:
    def debug_dump(self) -> str:
        return "trace"


class User(Base):
    pass
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_neg001_evaluation_fails_for_property_hit() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[None, does_not_have("email", member_kind="property")]
"""
    target = """
class User:
    @property
    def email(self) -> str:
        return "user@example.com"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "forbidden property 'email' is present" in results[0].message


def test_neg001_evaluation_fails_for_class_attribute_hit() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class Settings:
    __archtest__: Annotated[
        None,
        does_not_have("VERSION", member_kind="attribute", storage="class"),
    ]
"""
    target = """
class Settings:
    VERSION: str = "1"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Settings",
        target_kind="class",
        target_name="Settings",
        rule_id="NEG001/does_not_have/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "forbidden class attribute 'VERSION' is present" in results[0].message


def test_neg001_evaluation_fails_for_instance_attribute_hit() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have("password", member_kind="attribute", storage="instance"),
    ]
"""
    target = """
class User:
    def __init__(self) -> None:
        self.password: str = "secret"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "forbidden instance attribute 'password' is present" in results[0].message


def test_neg001_attribute_rule_ignores_property_only_target() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have("email", member_kind="attribute", storage="any"),
    ]
"""
    target = """
class User:
    @property
    def email(self) -> str:
        return "user@example.com"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_neg001_any_rule_fails_for_method_hit() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[None, does_not_have("debug_dump", member_kind="any")]
"""
    target = """
class User:
    def debug_dump(self) -> str:
        return "trace"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]


def test_neg001_any_rule_fails_for_property_hit() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[None, does_not_have("email", member_kind="any")]
"""
    target = """
class User:
    @property
    def email(self) -> str:
        return "user@example.com"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]


def test_neg001_any_rule_fails_for_attribute_hit() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[None, does_not_have("password", member_kind="any")]
"""
    target = """
class User:
    def __init__(self) -> None:
        self.password = "secret"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
