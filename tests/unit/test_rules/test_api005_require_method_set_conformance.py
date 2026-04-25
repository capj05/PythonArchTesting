from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_api005_regex_selection_passes_when_minimum_is_met() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class TestContract:
    __archtest__: Annotated[
        None,
        require_method_set(name_match="regex", pattern=r"test_.*", min_count=1),
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
        rule_id="API005/require_method_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["selected_count"] == 2
    assert results[0].details["failure_reason"] == "matching_method_set_within_bounds"


def test_api005_regex_selection_fails_when_no_matches_exist() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class TestContract:
    __archtest__: Annotated[
        None,
        require_method_set(name_match="regex", pattern=r"test_.*", min_count=1),
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
        rule_id="API005/require_method_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "no_matching_methods_found"
    assert results[0].details["selected_methods"] == []


def test_api005_names_selection_honors_exact_count_bounds() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class LifecycleContract:
    __archtest__: Annotated[
        None,
        require_method_set(
            name_match="names",
            names=["setUp", "tearDown"],
            min_count=2,
            max_count=2,
        ),
    ]
"""
    target = """
class LifecycleContract:
    def setUp(self) -> None:
        return None

    def tearDown(self) -> None:
        return None
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="LifecycleContract",
        target_kind="class",
        target_name="LifecycleContract",
        rule_id="API005/require_method_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["selected_count"] == 2


def test_api005_names_selection_fails_when_matching_count_exceeds_maximum() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class LifecycleContract:
    __archtest__: Annotated[
        None,
        require_method_set(
            name_match="names",
            names=["setUp", "tearDown", "beforeEach"],
            min_count=2,
            max_count=2,
        ),
    ]
"""
    target = """
class LifecycleContract:
    def setUp(self) -> None:
        return None

    def tearDown(self) -> None:
        return None

    def beforeEach(self) -> None:
        return None
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="LifecycleContract",
        target_kind="class",
        target_name="LifecycleContract",
        rule_id="API005/require_method_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "too_many_matching_methods"
    assert results[0].details["selected_count"] == 3


def test_api005_declared_only_excludes_inherited_methods() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class HookContract:
    __archtest__: Annotated[
        None,
        require_method_set(
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
        rule_id="API005/require_method_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "no_matching_methods_found"


def test_api005_inherited_methods_count_when_declared_only_is_false() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class HookContract:
    __archtest__: Annotated[
        None,
        require_method_set(
            name_match="regex",
            pattern=r"hook_.*",
            declared_only=False,
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
        rule_id="API005/require_method_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["selected_count"] == 1
    assert results[0].details["selected_methods"][0]["origin"] == "inherited"


def test_api005_method_kind_filter_counts_only_classmethods() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class FactoryContract:
    __archtest__: Annotated[
        None,
        require_method_set(
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
        rule_id="API005/require_method_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["selected_methods"][0]["method_kind"] == "class"


def test_api005_reporting_includes_full_selected_method_set() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class TestContract:
    __archtest__: Annotated[
        None,
        require_method_set(
            name_match="regex",
            pattern=r"test_.*",
            min_count=2,
            max_count=2,
        ),
    ]
"""
    target = """
class Base:
    def test_alpha(self) -> None:
        return None


class TestContract(Base):
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
        rule_id="API005/require_method_set/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert [item["name"] for item in results[0].details["selected_methods"]] == [
        "test_alpha",
        "test_beta",
    ]
    assert {item["origin"] for item in results[0].details["selected_methods"]} == {
        "declared",
        "inherited",
    }
