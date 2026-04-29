from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_api006_attribute_class_storage_selection() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Config:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("attribute",),
            storage="class",
            min_count=1,
        ),
    ]
"""
    target = """
class Config:
    VERSION: str = "1"
    NAME: str = "demo"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Config",
        target_kind="class",
        target_name="Config",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["selected_count"] == 2
    assert {item["member_kind"] for item in results[0].details["selected_members"]} == {
        "attribute"
    }
    assert {item["storage"] for item in results[0].details["selected_members"]} == {
        "class"
    }


def test_api006_attribute_instance_storage_selection() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class User:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("attribute",),
            storage="instance",
            min_count=1,
        ),
    ]
"""
    target = """
class User:
    def __init__(self) -> None:
        self.email: str = "user@example.com"
        self.name: str = "user"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["selected_count"] >= 2
    assert {item["storage"] for item in results[0].details["selected_members"]} == {
        "instance"
    }


def test_api006_attribute_property_selection() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class User:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("property",),
            min_count=1,
        ),
    ]
"""
    target = """
class User:
    @property
    def email(self) -> str:
        return self._email

    @property
    def name(self) -> str:
        return self._name

    def helper(self) -> None:
        return None
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["selected_count"] == 2
    assert {item["member_kind"] for item in results[0].details["selected_members"]} == {
        "property"
    }


def test_api006_attribute_descriptor_selection_via_cached_property() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class User:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("descriptor",),
            descriptor_kinds=("cached_property",),
            min_count=1,
        ),
    ]
"""
    target = """
from functools import cached_property

class User:
    @cached_property
    def expensive_value(self) -> int:
        return 42
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["selected_count"] == 1
    assert (
        results[0].details["selected_members"][0]["descriptor_kind"]
        == "cached_property"
    )


def test_api006_attribute_declared_only_excludes_inherited() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Config:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("attribute",),
            storage="class",
            declared_only=True,
            min_count=1,
        ),
    ]
"""
    target = """
class Base:
    VERSION: str = "1"


class Config(Base):
    pass
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Config",
        target_kind="class",
        target_name="Config",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "no_matching_members_found"


def test_api006_attribute_no_attributes_emits_failure() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Config:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("attribute",),
            min_count=1,
        ),
    ]
"""
    target = """
class Config:
    def helper(self) -> None:
        return None
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Config",
        target_kind="class",
        target_name="Config",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "no_matching_members_found"
