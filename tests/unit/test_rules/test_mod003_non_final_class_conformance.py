from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_mod003_non_final_class_passes_for_plain_class() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_class

class Contract:
    __archtest__: Annotated[None, is_non_final_class()]
"""
    target = """
class Contract:
    pass
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="MOD003/is_non_final_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["recognized_final_decorator"] is None
    assert results[0].details["modifier_polarity"] == "negative"
    assert results[0].details["failure_reason"] == "forbidden_final_class_absent"
    assert results[0].details["modifier_kind"] == "non_final_class"


def test_mod003_non_final_class_passes_for_unrelated_decorator() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_class

class Contract:
    __archtest__: Annotated[None, is_non_final_class()]
"""
    target = """
from dataclasses import dataclass

@dataclass
class Contract:
    name: str = "demo"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="MOD003/is_non_final_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_mod003_non_final_class_fails_for_typing_final_decorator() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_class

class Contract:
    __archtest__: Annotated[None, is_non_final_class()]
"""
    target = """
from typing import final

@final
class Contract:
    pass
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="MOD003/is_non_final_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["recognized_final_decorator"] == "typing.final"
    assert results[0].details["modifier_polarity"] == "negative"
    assert results[0].details["failure_reason"] == "forbidden_final_class_present"


def test_mod003_non_final_class_fails_for_typing_qualified_decorator() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_class

class Contract:
    __archtest__: Annotated[None, is_non_final_class()]
"""
    target = """
import typing

@typing.final
class Contract:
    pass
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="MOD003/is_non_final_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["recognized_final_decorator"] == "typing.final"
    assert results[0].details["failure_reason"] == "forbidden_final_class_present"


def test_mod003_non_final_class_fails_for_typing_extensions_alias() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_class

class Contract:
    __archtest__: Annotated[None, is_non_final_class()]
"""
    target = """
from typing_extensions import final as ext_final

@ext_final
class Contract:
    pass
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id="MOD003/is_non_final_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["recognized_final_decorator"] == "typing_extensions.final"
    assert results[0].details["failure_reason"] == "forbidden_final_class_present"


def test_mod003_non_final_class_method_only_final_does_not_fail() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_class

class Contract:
    __archtest__: Annotated[None, is_non_final_class()]
"""
    target = """
from typing import final

class Contract:
    @final
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
        rule_id="MOD003/is_non_final_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
