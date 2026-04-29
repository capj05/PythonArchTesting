from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_api006_method_regex_selection_passes_when_minimum_is_met() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class TestContract:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("method",),
            name_match="regex",
            pattern=r"test_.*",
            min_count=1,
        ),
    ]
"""
    target = """
class TestContract:
    def test_alpha(self) -> None:
        return None

    def helper(self) -> None:
        return None

    def test_beta(self) -> None:
        return None
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="TestContract",
        target_kind="class",
        target_name="TestContract",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["selected_count"] == 2
    assert results[0].details["failure_reason"] == "matching_member_set_within_bounds"
    assert {item["member_kind"] for item in results[0].details["selected_members"]} == {
        "method"
    }


def test_api006_method_classmethod_only_filter() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class FactoryContract:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("method",),
            name_match="regex",
            pattern=r"create_.*",
            method_kind="classmethod",
            min_count=1,
            max_count=1,
        ),
    ]
"""
    target = """
class FactoryContract:
    @classmethod
    def create_from_name(cls, name: str) -> "FactoryContract":
        return cls()

    @staticmethod
    def create_static(name: str) -> "FactoryContract":
        return FactoryContract()

    def create_instance(self, name: str) -> "FactoryContract":
        return self
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="FactoryContract",
        target_kind="class",
        target_name="FactoryContract",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["selected_count"] == 1
    assert results[0].details["selected_members"][0]["method_kind"] == "class"


def test_api006_method_staticmethod_only_filter() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class UtilityContract:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("method",),
            method_kind="staticmethod",
            min_count=1,
        ),
    ]
"""
    target = """
class UtilityContract:
    @staticmethod
    def util_a() -> None:
        return None

    def instance_method(self) -> None:
        return None
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="UtilityContract",
        target_kind="class",
        target_name="UtilityContract",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["selected_count"] == 1
    assert results[0].details["selected_members"][0]["method_kind"] == "static"


def test_api006_method_declared_only_excludes_inherited() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class HookContract:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("method",),
            name_match="regex",
            pattern=r"hook_.*",
            declared_only=True,
            min_count=1,
        ),
    ]
"""
    target = """
class Base:
    def hook_prepare(self) -> None:
        return None


class HookContract(Base):
    pass
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="HookContract",
        target_kind="class",
        target_name="HookContract",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "no_matching_members_found"


def test_api006_method_max_count_overflow_fails() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class TestContract:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("method",),
            name_match="regex",
            pattern=r"test_.*",
            min_count=1,
            max_count=2,
        ),
    ]
"""
    target = """
class TestContract:
    def test_alpha(self) -> None:
        return None

    def test_beta(self) -> None:
        return None

    def test_gamma(self) -> None:
        return None
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="TestContract",
        target_kind="class",
        target_name="TestContract",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "too_many_matching_members"
    assert results[0].details["selected_count"] == 3


def test_api006_method_no_match_emits_failure() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class TestContract:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("method",),
            name_match="regex",
            pattern=r"test_.*",
            min_count=1,
        ),
    ]
"""
    target = """
class TestContract:
    def helper(self) -> None:
        return None
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="TestContract",
        target_kind="class",
        target_name="TestContract",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "no_matching_members_found"
    assert results[0].details["selected_members"] == []
