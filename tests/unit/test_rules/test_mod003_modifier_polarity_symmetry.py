from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def _evaluate_class_marker(
    *,
    marker_import: str,
    marker_name: str,
    rule_id: str,
    target_text: str,
) -> tuple[list[object], list[object], object]:
    source = f"""
from typing import Annotated
from pythonarchtesting.rules import {marker_import}

class Contract:
    __archtest__: Annotated[None, {marker_name}()]
"""
    return evaluate_single_rule(
        source_text=source,
        target_text=target_text,
        source_kind="class",
        source_name="Contract",
        target_kind="class",
        target_name="Contract",
        rule_id=rule_id,
    )


def _evaluate_method_marker(
    *,
    marker_import: str,
    marker_name: str,
    rule_id: str,
    target_text: str,
) -> tuple[list[object], list[object], object]:
    source = f"""
from typing import Annotated
from pythonarchtesting.rules import {marker_import}

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, {marker_name}()]
        return ""
"""
    return evaluate_single_rule(
        source_text=source,
        target_text=target_text,
        source_kind="method",
        source_name="render",
        target_kind="method",
        target_name="render",
        rule_id=rule_id,
    )


def test_mod003_final_class_symmetry_for_final_target() -> None:
    target = """
from typing import final

@final
class Contract:
    pass
"""

    pos_results, pos_errors, _ = _evaluate_class_marker(
        marker_import="is_final_class",
        marker_name="is_final_class",
        rule_id="MOD001/is_final_class/v1",
        target_text=target,
    )
    neg_results, neg_errors, _ = _evaluate_class_marker(
        marker_import="is_non_final_class",
        marker_name="is_non_final_class",
        rule_id="MOD003/is_non_final_class/v1",
        target_text=target,
    )

    assert pos_errors == [] and neg_errors == []
    assert [r.status for r in pos_results] == ["OK"]
    assert [r.status for r in neg_results] == ["FAILED"]
    assert pos_results[0].details["recognized_final_decorator"] == "typing.final"
    assert neg_results[0].details["recognized_final_decorator"] == "typing.final"
    assert neg_results[0].details["modifier_polarity"] == "negative"
    assert neg_results[0].details["failure_reason"] == "forbidden_final_class_present"


def test_mod003_final_class_symmetry_for_undecorated_target() -> None:
    target = """
class Contract:
    pass
"""

    pos_results, pos_errors, _ = _evaluate_class_marker(
        marker_import="is_final_class",
        marker_name="is_final_class",
        rule_id="MOD001/is_final_class/v1",
        target_text=target,
    )
    neg_results, neg_errors, _ = _evaluate_class_marker(
        marker_import="is_non_final_class",
        marker_name="is_non_final_class",
        rule_id="MOD003/is_non_final_class/v1",
        target_text=target,
    )

    assert pos_errors == [] and neg_errors == []
    assert [r.status for r in pos_results] == ["FAILED"]
    assert [r.status for r in neg_results] == ["OK"]
    assert pos_results[0].details["recognized_final_decorator"] is None
    assert neg_results[0].details["recognized_final_decorator"] is None
    assert neg_results[0].details["modifier_polarity"] == "negative"
    assert neg_results[0].details["failure_reason"] == "forbidden_final_class_absent"


def test_mod003_abstract_method_symmetry_for_abstract_target() -> None:
    target = """
from abc import abstractmethod

class Contract:
    @abstractmethod
    def render(self) -> str:
        ...
"""

    pos_results, pos_errors, _ = _evaluate_method_marker(
        marker_import="is_abstract_method",
        marker_name="is_abstract_method",
        rule_id="MOD002/is_abstract_method/v1",
        target_text=target,
    )
    neg_results, neg_errors, _ = _evaluate_method_marker(
        marker_import="is_non_abstract_method",
        marker_name="is_non_abstract_method",
        rule_id="MOD003/is_non_abstract_method/v1",
        target_text=target,
    )

    assert pos_errors == [] and neg_errors == []
    assert [r.status for r in pos_results] == ["OK"]
    assert [r.status for r in neg_results] == ["FAILED"]
    assert pos_results[0].details["recognized_abstract_decorator"] == "abc.abstractmethod"
    assert neg_results[0].details["recognized_abstract_decorator"] == "abc.abstractmethod"
    assert neg_results[0].details["modifier_polarity"] == "negative"
    assert neg_results[0].details["failure_reason"] == "forbidden_abstract_method_present"


def test_mod003_abstract_method_symmetry_for_concrete_target() -> None:
    target = """
class Contract:
    def render(self) -> str:
        return "ok"
"""

    pos_results, pos_errors, _ = _evaluate_method_marker(
        marker_import="is_abstract_method",
        marker_name="is_abstract_method",
        rule_id="MOD002/is_abstract_method/v1",
        target_text=target,
    )
    neg_results, neg_errors, _ = _evaluate_method_marker(
        marker_import="is_non_abstract_method",
        marker_name="is_non_abstract_method",
        rule_id="MOD003/is_non_abstract_method/v1",
        target_text=target,
    )

    assert pos_errors == [] and neg_errors == []
    assert [r.status for r in pos_results] == ["FAILED"]
    assert [r.status for r in neg_results] == ["OK"]
    assert pos_results[0].details["recognized_abstract_decorator"] is None
    assert neg_results[0].details["recognized_abstract_decorator"] is None
    assert neg_results[0].details["modifier_polarity"] == "negative"
    assert neg_results[0].details["failure_reason"] == "forbidden_abstract_method_absent"


def test_mod003_final_method_symmetry_for_final_target() -> None:
    target = """
from typing import final

class Contract:
    @final
    def render(self) -> str:
        return "ok"
"""

    pos_results, pos_errors, _ = _evaluate_method_marker(
        marker_import="is_final_method",
        marker_name="is_final_method",
        rule_id="MOD002/is_final_method/v1",
        target_text=target,
    )
    neg_results, neg_errors, _ = _evaluate_method_marker(
        marker_import="is_non_final_method",
        marker_name="is_non_final_method",
        rule_id="MOD003/is_non_final_method/v1",
        target_text=target,
    )

    assert pos_errors == [] and neg_errors == []
    assert [r.status for r in pos_results] == ["OK"]
    assert [r.status for r in neg_results] == ["FAILED"]
    assert pos_results[0].details["recognized_final_decorator"] == "typing.final"
    assert neg_results[0].details["recognized_final_decorator"] == "typing.final"
    assert neg_results[0].details["modifier_polarity"] == "negative"
    assert neg_results[0].details["failure_reason"] == "forbidden_final_method_present"


def test_mod003_final_method_symmetry_for_plain_target() -> None:
    target = """
class Contract:
    def render(self) -> str:
        return "ok"
"""

    pos_results, pos_errors, _ = _evaluate_method_marker(
        marker_import="is_final_method",
        marker_name="is_final_method",
        rule_id="MOD002/is_final_method/v1",
        target_text=target,
    )
    neg_results, neg_errors, _ = _evaluate_method_marker(
        marker_import="is_non_final_method",
        marker_name="is_non_final_method",
        rule_id="MOD003/is_non_final_method/v1",
        target_text=target,
    )

    assert pos_errors == [] and neg_errors == []
    assert [r.status for r in pos_results] == ["FAILED"]
    assert [r.status for r in neg_results] == ["OK"]
    assert pos_results[0].details["recognized_final_decorator"] is None
    assert neg_results[0].details["recognized_final_decorator"] is None
    assert neg_results[0].details["modifier_polarity"] == "negative"
    assert neg_results[0].details["failure_reason"] == "forbidden_final_method_absent"
