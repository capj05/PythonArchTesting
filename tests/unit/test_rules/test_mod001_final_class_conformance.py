from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_mod001_final_class_passes_for_typing_final_import() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_final_class

class Contract:
    __archtest__: Annotated[None, is_final_class()]
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
        rule_id="MOD001/is_final_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["recognized_final_decorator"] == "typing.final"


def test_mod001_final_class_passes_for_typing_qualified_decorator() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_final_class

class Contract:
    __archtest__: Annotated[None, is_final_class()]
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
        rule_id="MOD001/is_final_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["recognized_final_decorator"] == "typing.final"


def test_mod001_final_class_passes_for_typing_extensions_final() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_final_class

class Contract:
    __archtest__: Annotated[None, is_final_class()]
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
        rule_id="MOD001/is_final_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["recognized_final_decorator"] == "typing_extensions.final"


def test_mod001_undecorated_class_fails_final_class_rule() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_final_class

class Contract:
    __archtest__: Annotated[None, is_final_class()]
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
        rule_id="MOD001/is_final_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["recognized_final_decorator"] is None


def test_mod001_method_level_final_does_not_satisfy_class_rule() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_final_class

class Contract:
    __archtest__: Annotated[None, is_final_class()]
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
        rule_id="MOD001/is_final_class/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["normalized_decorators"] == []
