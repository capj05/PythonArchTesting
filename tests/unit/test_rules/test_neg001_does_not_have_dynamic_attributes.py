from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_neg001_dynamic_instance_setattr_detected_when_enabled() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have(
            "token",
            member_kind="attribute",
            storage="instance",
            include_dynamic_attributes=True,
        ),
    ]
"""
    target = """
class User:
    def __init__(self, token: str) -> None:
        setattr(self, "token", token)
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v2",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["hits"][0]["origin"] == "dynamic_setattr_instance"


def test_neg001_dynamic_class_setattr_detected_when_enabled() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have(
            "token",
            member_kind="attribute",
            storage="class",
            include_dynamic_attributes=True,
        ),
    ]
"""
    target = """
class User:
    @classmethod
    def configure(cls, token: str) -> None:
        setattr(cls, "token", token)
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v2",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["hits"][0]["origin"] == "dynamic_setattr_class"


def test_neg001_dynamic_attribute_detection_stays_off_by_default() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have("token", member_kind="attribute", storage="instance"),
    ]
"""
    target = """
class User:
    def __init__(self, token: str) -> None:
        setattr(self, "token", token)
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


def test_neg001_dynamic_attribute_detection_ignores_computed_name() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have(
            "token",
            member_kind="attribute",
            storage="instance",
            include_dynamic_attributes=True,
        ),
    ]
"""
    target = """
class User:
    def __init__(self, token: str) -> None:
        attr = "token"
        setattr(self, attr, token)
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v2",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_neg001_dynamic_attribute_detection_ignores_helper_wrapper() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have(
            "token",
            member_kind="attribute",
            storage="instance",
            include_dynamic_attributes=True,
        ),
    ]
"""
    target = """
def assign_token(target: object, value: str) -> None:
    setattr(target, "token", value)


class User:
    def __init__(self, token: str) -> None:
        assign_token(self, token)
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v2",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_neg001_descriptor_attribute_detected_only_when_enabled() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have(
            "token",
            member_kind="attribute",
            storage="class",
            include_descriptors=True,
        ),
    ]
"""
    target = """
class SecretDescriptor:
    def __get__(self, instance, owner):
        return "secret"


class User:
    token = SecretDescriptor()
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="NEG001/does_not_have/v2",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["hits"][0]["origin"] == "descriptor_assign"


def test_neg001_descriptor_attribute_detection_stays_off_by_default() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have("token", member_kind="attribute", storage="class"),
    ]
"""
    target = """
class SecretDescriptor:
    def __get__(self, instance, owner):
        return "secret"


class User:
    token = SecretDescriptor()
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
