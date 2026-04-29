from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_mod003_non_final_method_passes_for_plain_method() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_non_final_method()]
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
        rule_id="MOD003/is_non_final_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["recognized_final_decorator"] is None
    assert results[0].details["modifier_polarity"] == "negative"
    assert results[0].details["failure_reason"] == "forbidden_final_method_absent"
    assert results[0].details["modifier_kind"] == "non_final_method"


def test_mod003_non_final_method_fails_for_typing_final() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_non_final_method()]
        return ""
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
        source_kind="method",
        source_name="render",
        target_kind="method",
        target_name="render",
        rule_id="MOD003/is_non_final_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["recognized_final_decorator"] == "typing.final"
    assert results[0].details["modifier_polarity"] == "negative"
    assert results[0].details["failure_reason"] == "forbidden_final_method_present"


def test_mod003_non_final_method_fails_for_typing_qualified_decorator() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_non_final_method()]
        return ""
"""
    target = """
import typing

class Contract:
    @typing.final
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
        rule_id="MOD003/is_non_final_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["recognized_final_decorator"] == "typing.final"
    assert results[0].details["failure_reason"] == "forbidden_final_method_present"


def test_mod003_non_final_method_fails_for_typing_extensions_alias() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_non_final_method()]
        return ""
"""
    target = """
from typing_extensions import final as ext_final

class Contract:
    @ext_final
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
        rule_id="MOD003/is_non_final_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["recognized_final_decorator"] == "typing_extensions.final"
    assert results[0].details["failure_reason"] == "forbidden_final_method_present"


def test_mod003_non_final_method_class_only_final_does_not_fail() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_non_final_method()]
        return ""
"""
    target = """
from typing import final

@final
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
        rule_id="MOD003/is_non_final_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_mod003_non_final_method_fails_for_final_classmethod_combo() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_method

class Contract:
    @classmethod
    def create(cls) -> "Contract":
        __archtest__: Annotated[None, is_non_final_method()]
        return cls()
"""
    target = """
from typing import final

class Contract:
    @classmethod
    @final
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
        rule_id="MOD003/is_non_final_method/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["recognized_final_decorator"] == "typing.final"
    assert results[0].details["failure_reason"] == "forbidden_final_method_present"
