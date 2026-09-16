"""Target: target_pass_property_count — PropertyHolder keeps exactly 2 properties."""

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
    # Exactly 2 properties — within [2, 2].
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
