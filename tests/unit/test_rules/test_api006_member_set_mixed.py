from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_api006_mixed_method_and_attribute_kinds() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("method", "attribute"),
            min_count=2,
        ),
    ]
"""
    target = """
class Contract:
    VERSION: str = "1"

    def run(self) -> None:
        return None
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    kinds = {item["member_kind"] for item in results[0].details["selected_members"]}
    assert kinds == {"method", "attribute"}


def test_api006_any_member_kind_selects_all_families() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("any",),
            min_count=1,
        ),
    ]
"""
    target = """
class Contract:
    VERSION: str = "1"

    def __init__(self, name: str) -> None:
        self.name = name

    @property
    def display_name(self) -> str:
        return self.name

    def run(self) -> None:
        return None
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    kinds = {item["member_kind"] for item in results[0].details["selected_members"]}
    assert {"method", "attribute", "property", "constructor"} <= kinds


def test_api006_attribute_and_property_kinds() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("attribute", "property"),
            min_count=2,
        ),
    ]
"""
    target = """
class Contract:
    NAME: str = "demo"

    @property
    def display(self) -> str:
        return self.NAME
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    kinds = {item["member_kind"] for item in results[0].details["selected_members"]}
    assert kinds == {"attribute", "property"}


def test_api006_regex_filter_across_member_families() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("method", "attribute"),
            name_match="regex",
            pattern=r"data_.*",
            min_count=2,
        ),
    ]
"""
    target = """
class Contract:
    data_name: str = "demo"
    helper_value: int = 0

    def data_run(self) -> None:
        return None

    def helper(self) -> None:
        return None
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    names = {item["name"] for item in results[0].details["selected_members"]}
    assert names == {"data_name", "data_run"}


def test_api006_selected_members_are_sorted_deterministically() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("method", "attribute"),
            min_count=1,
        ),
    ]
"""
    target = """
class Contract:
    zebra: str = "z"
    alpha: str = "a"

    def yankee(self) -> None:
        return None

    def bravo(self) -> None:
        return None
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="API006/require_member_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    selected = results[0].details["selected_members"]
    keys = [(item["member_kind"], item["name"]) for item in selected]
    assert keys == sorted(keys)
