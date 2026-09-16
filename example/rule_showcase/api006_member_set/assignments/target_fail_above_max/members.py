"""Target: target_fail_above_max — PropertyHolder gains a 3rd property (> max_count=2)."""

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
    # 3 properties — exceeds max_count=2.
    @property
    def first(self) -> int:
        return 0

    @property
    def second(self) -> int:
        return 0

    @property
    def third(self) -> int:
        return 0


class MethodOnly:
    def step_a(self) -> None:
        return None

    def step_b(self) -> None:
        return None
