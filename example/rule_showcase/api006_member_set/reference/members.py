"""Reference module for the API006 / require_member_set showcase.

One ``require_member_set`` marker per class so each target isolates a single
concern (member-kind filtering, dataclass field interpretation, property
counting bounds, allow_property toggle).
"""

from dataclasses import dataclass
from typing import Annotated

from pythonarchtesting.rules import require_member_set


class MixedMembers:
    """At least 3 members regardless of kind (3 <= count <= 10)."""

    __archtest__: Annotated[
        None,
        require_member_set(member_kinds=("any",), min_count=3, max_count=10),
    ]

    NAME: str = "X"

    def method_a(self) -> None:
        return None

    @property
    def value(self) -> int:
        return 0


@dataclass
class DataclassPayload:
    """Dataclass fields counted as attributes (2 <= count <= 5)."""

    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("attribute",),
            interpret_dataclass_fields=True,
            min_count=2,
            max_count=5,
        ),
    ]

    a: int = 0
    b: str = ""
    c: float = 0.0


class PropertyHolder:
    """Exactly 2 properties (min_count == max_count == 2)."""

    __archtest__: Annotated[
        None,
        require_member_set(member_kinds=("property",), min_count=2, max_count=2),
    ]

    @property
    def first(self) -> int:
        return 0

    @property
    def second(self) -> int:
        return 0


class MethodOnly:
    """Methods only — properties are forbidden via ``allow_property=False``."""

    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("method",),
            allow_property=False,
            min_count=2,
        ),
    ]

    def step_a(self) -> None:
        return None

    def step_b(self) -> None:
        return None
