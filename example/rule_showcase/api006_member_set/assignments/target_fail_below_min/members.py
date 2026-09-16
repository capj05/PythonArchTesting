"""Target: target_fail_below_min — MixedMembers reduced to only 2 members (< min_count=3)."""

from dataclasses import dataclass


class MixedMembers:
    # Only 2 members in total — below the min_count=3 bound.
    NAME: str = "X"

    def method_a(self) -> None:
        return None


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
    def step_a(self) -> None:
        return None

    def step_b(self) -> None:
        return None
