"""Characterisation tests for the API003 failure classification.

Each test pins the ``fail_code`` and the ``candidate_attributes`` payload that
one branch of the required-attribute failure cascade reports, so that a
refactor of the evaluator cannot silently change what lands in the report.
"""

from __future__ import annotations

from typing import Any

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule

_CANDIDATE_KEYS = (
    "name",
    "annotation",
    "storage",
    "declared_on_qualname",
    "inherited",
    "is_writable",
    "origin",
    "descriptor_kind",
)


def _evaluate(marker: str, target: str) -> Any:
    """Evaluate one ``required_attribute`` marker against a ``User`` target.

    The marker is spliced into a reference class so each test only states the
    rule arguments and the target class it is checked against.
    """
    source = f"""
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[None, {marker}]
"""
    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
    )
    assert errors == []
    assert len(results) == 1
    return results[0]


def _candidates(result: Any) -> list[tuple[Any, ...]]:
    """Project the candidate payloads onto the fields that identify a member.

    Line numbers are left out because they only restate the fixture layout.
    """
    return [
        tuple(candidate[key] for key in _CANDIDATE_KEYS)
        for candidate in result.details["candidate_attributes"]
    ]


def test_api003_missing_attribute_reports_missing_code_and_no_candidates() -> None:
    result = _evaluate(
        'required_attribute("email")',
        """
class User:
    name: str = "n"
""",
    )

    assert result.status == "FAILED"
    assert result.details["fail_code"] == "missing_attribute_or_property"
    assert result.details["reason"] == "missing required attribute 'email'"
    assert result.details["candidate_attributes"] == []
    assert result.details["matched_attribute"] is None


def test_api003_optional_missing_attribute_is_skipped_without_fail_code() -> None:
    result = _evaluate(
        'required_attribute("email", allow_missing=True)',
        """
class User:
    name: str = "n"
""",
    )

    assert result.status == "SKIPPED"
    assert "fail_code" not in result.details
    assert result.details["failure_reason"] == "optional_member_absent"
    assert result.details["candidate_attributes"] == []


def test_api003_storage_mismatch_reports_code_and_every_candidate() -> None:
    result = _evaluate(
        'required_attribute("VERSION", storage="instance")',
        """
class Base:
    VERSION: int = 0

class User(Base):
    VERSION: str = "1"
""",
    )

    assert result.status == "FAILED"
    assert result.details["fail_code"] == "storage_mismatch"
    assert result.details["reason"] == (
        "attribute storage mismatch for 'VERSION': required instance, found class"
    )
    assert _candidates(result) == [
        ("VERSION", "str", "class", "User", False, True, "class_annassign", None),
        ("VERSION", "int", "class", "Base", True, True, "class_annassign", None),
    ]


def test_api003_property_without_allow_property_reports_not_allowed_code() -> None:
    result = _evaluate(
        'required_attribute("email")',
        """
class User:
    @property
    def email(self) -> str:
        return "e"
""",
    )

    assert result.status == "FAILED"
    assert result.details["fail_code"] == "property_present_but_not_allowed"
    assert _candidates(result) == [
        ("email", "str", "property", "User", False, False, "property", None),
    ]


def test_api003_read_only_property_reports_read_only_code() -> None:
    result = _evaluate(
        'required_attribute("email", allow_property=True, require_writable=True)',
        """
class User:
    @property
    def email(self) -> str:
        return "e"
""",
    )

    assert result.status == "FAILED"
    assert result.details["fail_code"] == "attribute_present_but_read_only"
    assert result.details["reason"] == (
        "property 'email' is read-only (no setter); "
        "require_writable=True requires a setter"
    )
    assert _candidates(result) == [
        ("email", "str", "property", "User", False, False, "property", None),
    ]


def test_api003_annotation_mismatch_reports_mismatch_code_and_first_reason() -> None:
    result = _evaluate(
        'required_attribute("x", annotation="bytes")',
        """
class Base:
    x: str = "b"

class User(Base):
    x: int = 1
""",
    )

    assert result.status == "FAILED"
    assert result.details["fail_code"] == "attribute_present_but_annotation_mismatch"
    # The reason describes the first candidate tried, not the last one.
    assert result.details["reason"] == (
        "attribute annotation mismatch: expected bytes, found int"
    )
    assert _candidates(result) == [
        ("x", "int", "class", "User", False, True, "class_annassign", None),
        ("x", "str", "class", "Base", True, True, "class_annassign", None),
    ]


def test_api003_mixed_failures_pair_read_only_reason_with_mismatch_code() -> None:
    """Pin the current pairing of a read-only reason with a mismatch code.

    The child's read-only property is tried first and fails on writability;
    the inherited writable attribute then fails on its annotation.  Because
    not every candidate is read-only the code says annotation mismatch, while
    the reason still carries the first, read-only, failure.
    """
    result = _evaluate(
        'required_attribute("z", annotation="int", allow_property=True, '
        "require_writable=True)",
        """
class Base:
    z: str = "zz"

class User(Base):
    @property
    def z(self) -> int:
        return 1
""",
    )

    assert result.status == "FAILED"
    assert result.details["fail_code"] == "attribute_present_but_annotation_mismatch"
    assert result.details["reason"] == (
        "property 'z' is read-only (no setter); "
        "require_writable=True requires a setter"
    )
    assert _candidates(result) == [
        ("z", "int", "property", "User", False, False, "property", None),
        ("z", "str", "class", "Base", True, True, "class_annassign", None),
    ]


def test_api003_success_lists_every_candidate_including_rejected_ones() -> None:
    result = _evaluate(
        'required_attribute("x", annotation="int", storage="class")',
        """
class User:
    x: int = 1

    def __init__(self) -> None:
        self.x: str = "s"
""",
    )

    assert result.status == "OK"
    assert "fail_code" not in result.details
    assert result.details["matched_attribute"]["storage"] == "class"
    assert [c[2] for c in _candidates(result)] == ["class", "instance"]
