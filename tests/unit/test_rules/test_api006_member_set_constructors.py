from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_api006_constructor_init_auto_selects_declared_init() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class User:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("constructor",),
            min_count=1,
        ),
    ]
"""
    target = """
class User:
    def __init__(self, name: str) -> None:
        self.name = name
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
    assert results[0].details["selected_members"][0]["member_kind"] == "constructor"
    assert results[0].details["selected_members"][0]["name"] == "__init__"


def test_api006_constructor_kind_init_only_filter() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Resource:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("constructor",),
            constructor_kind="__init__",
            min_count=1,
            max_count=1,
        ),
    ]
"""
    target = """
class Resource:
    def __init__(self, name: str) -> None:
        self.name = name

    def __new__(cls, name: str) -> "Resource":
        return super().__new__(cls)
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Resource",
        target_kind="class",
        target_name="Resource",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["selected_count"] == 1
    assert results[0].details["selected_members"][0]["name"] == "__init__"


def test_api006_constructor_kind_new_only_filter() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Resource:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("constructor",),
            constructor_kind="__new__",
            min_count=1,
            max_count=1,
        ),
    ]
"""
    target = """
class Resource:
    def __init__(self, name: str) -> None:
        self.name = name

    def __new__(cls, name: str) -> "Resource":
        return super().__new__(cls)
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Resource",
        target_kind="class",
        target_name="Resource",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["selected_count"] == 1
    assert results[0].details["selected_members"][0]["name"] == "__new__"


def test_api006_constructor_dataclass_generated_included_by_default() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Config:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("constructor",),
            min_count=1,
        ),
    ]
"""
    target = """
from dataclasses import dataclass

@dataclass
class Config:
    name: str
    version: str = "1"
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
    assert results[0].details["selected_count"] >= 1
    origins = {item["origin"] for item in results[0].details["selected_members"]}
    assert "generated_dataclass_init" in origins


def test_api006_constructor_dataclass_generated_excluded_when_flag_false() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Config:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("constructor",),
            include_dataclass_constructor=False,
            min_count=1,
        ),
    ]
"""
    target = """
from dataclasses import dataclass

@dataclass
class Config:
    name: str
    version: str = "1"
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


def test_api006_constructor_declared_only_excludes_inherited() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class User:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("constructor",),
            declared_only=True,
            min_count=1,
        ),
    ]
"""
    target = """
class Base:
    def __init__(self, name: str) -> None:
        self.name = name


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
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "no_matching_members_found"
