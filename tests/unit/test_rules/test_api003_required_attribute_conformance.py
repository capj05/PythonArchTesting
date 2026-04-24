from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import evaluate_single_rule


def test_api003_evaluation_passes_for_class_attribute() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("VERSION", annotation="str", storage="class"),
    ]
"""
    target = """
class User:
    VERSION: str = "1"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api003_evaluation_passes_for_instance_attribute() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", annotation="str", storage="instance"),
    ]
"""
    target = """
class User:
    def __init__(self) -> None:
        self.email: str = "user@example.com"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api003_evaluation_passes_for_inherited_attribute() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("VERSION", annotation="str", storage="class"),
    ]
"""
    target = """
class Base:
    VERSION: str = "1"


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
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api003_evaluation_fails_for_missing_attribute() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[None, required_attribute("email", storage="instance")]
"""
    target = """
class User:
    pass
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "missing required attribute 'email'" in results[0].message


def test_api003_evaluation_fails_for_wrong_storage() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", annotation="str", storage="class"),
    ]
"""
    target = """
class User:
    def __init__(self) -> None:
        self.email: str = "user@example.com"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "attribute storage mismatch" in results[0].message


def test_api003_evaluation_fails_for_annotation_mismatch() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("VERSION", annotation="int", storage="class"),
    ]
"""
    target = """
class User:
    VERSION: str = "1"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "attribute annotation mismatch" in results[0].message


def test_api003_evaluation_fails_for_property_only_target() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", annotation="str", storage="any"),
    ]
"""
    target = """
class User:
    @property
    def email(self) -> str:
        return "user@example.com"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "properties do not satisfy required_attribute" in results[0].message


def test_api003_evaluation_passes_for_presence_only_unannotated_attribute() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[None, required_attribute("VERSION", storage="class")]
"""
    target = """
class User:
    VERSION = "1"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api003_property_passes_when_allow_property_true() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", allow_property=True),
    ]
"""
    target = """
class User:
    @property
    def email(self) -> str:
        return "user@example.com"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api003_property_fails_when_allow_property_false() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", allow_property=False),
    ]
"""
    target = """
class User:
    @property
    def email(self) -> str:
        return "user@example.com"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "properties do not satisfy" in results[0].message


def test_api003_writable_property_passes_require_writable() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", allow_property=True, require_writable=True),
    ]
"""
    target = """
class User:
    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, value: str) -> None:
        self._email = value
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api003_read_only_property_fails_require_writable() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", allow_property=True, require_writable=True),
    ]
"""
    target = """
class User:
    @property
    def email(self) -> str:
        return "user@example.com"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "read-only" in results[0].message


def test_api003_attribute_passes_require_writable() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", require_writable=True, storage="instance"),
    ]
"""
    target = """
class User:
    def __init__(self) -> None:
        self.email: str = "user@example.com"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api003_declared_only_fails_if_only_inherited() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("VERSION", storage="class", declared_only=True),
    ]
"""
    target = """
class Base:
    VERSION: str = "1"


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
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "missing required attribute 'VERSION'" in results[0].message


def test_api003_declared_only_passes_if_directly_declared() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("VERSION", storage="class", declared_only=True),
    ]
"""
    target = """
class User:
    VERSION: str = "1"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api003_getter_method_does_not_satisfy() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", allow_property=True),
    ]
"""
    target = """
class User:
    def get_email(self) -> str:
        return "user@example.com"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "missing required attribute 'email'" in results[0].message


def test_api003_property_annotation_mismatch_fails() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", annotation="int", allow_property=True),
    ]
"""
    target = """
class User:
    @property
    def email(self) -> str:
        return "user@example.com"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "annotation mismatch" in results[0].message


def test_api003_attribute_wins_over_property_when_both_present() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", allow_property=True),
    ]
"""
    target = """
class User:
    email: str = ""

    @property
    def email(self) -> str:  # type: ignore[override]
        return self.__dict__.get("_email", "")
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api003_allow_property_with_instance_storage() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", storage="instance", allow_property=True),
    ]
"""
    target = """
class User:
    @property
    def email(self) -> str:
        return "user@example.com"
"""

    results, errors, _ = evaluate_single_rule(
        source_text=source,
        target_text=target,
        source_kind="class",
        source_name="User",
        target_kind="class",
        target_name="User",
        rule_id="API003/required_attribute/v1",
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
