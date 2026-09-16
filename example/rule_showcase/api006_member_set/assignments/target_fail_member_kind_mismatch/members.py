"""Target: target_fail_member_kind_mismatch — MethodOnly replaces methods with constants.

The rule requires member_kinds=("method",) with min_count=2; replacing both methods
with class-level constants drops the method count to 0.
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
    # No methods — 2 class-level constants instead. method count = 0 < min_count=2.
    STEP_A: str = "a"
    STEP_B: str = "b"
