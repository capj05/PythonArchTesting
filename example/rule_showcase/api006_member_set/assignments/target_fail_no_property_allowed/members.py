"""Target: target_fail_no_property_allowed — MethodOnly adds a @property.

The marker forbids properties (allow_property=False). Replacing one method with
a property leaves only 1 method (below min_count=2) AND surfaces a forbidden
property.
"""

from dataclasses import dataclass


class MixedMembers:
    NAME: str = "X"

    def method_a(self) -> None:
        return None

    @property
    def value(self) -> int:
        return 0


@dataclass
class DataclassPayload:
    a: int = 0
    b: str = ""
    c: float = 0.0


class PropertyHolder:
    @property
    def first(self) -> int:
        return 0

    @property
    def second(self) -> int:
        return 0


class MethodOnly:
    # step_b removed; replaced by a @property which allow_property=False forbids.
    def step_a(self) -> None:
        return None

    @property
    def step_b(self) -> int:
        return 0
