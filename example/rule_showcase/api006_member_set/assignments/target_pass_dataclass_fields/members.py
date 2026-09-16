"""Target: target_pass_dataclass_fields — DataclassPayload keeps 3 fields (within 2-5)."""

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
    # 3 dataclass fields — interpret_dataclass_fields counts these as attributes,
    # so the [2..5] bound on attributes passes.
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
