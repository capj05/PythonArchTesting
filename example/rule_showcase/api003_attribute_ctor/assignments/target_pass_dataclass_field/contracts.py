"""target_pass_dataclass_field — dataclass field satisfies required_attribute."""

from dataclasses import dataclass


class HasName:
    def __init__(self, name: str) -> None:
        self.name: str = name


class HasVersion:
    VERSION: str = "1.0"


class HasPropertyOk:
    @property
    def size(self) -> int:
        return 0


@dataclass
class HasDataclassField:
    # ``interpret_dataclass_fields=True`` lets this field satisfy the attr rule.
    count: int = 0


class HasCompatibleCtor:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class HasExactCtor:
    def __init__(self, x: int) -> None:
        self.x = x


class _CtorBase:
    def __init__(self, value: int) -> None:
        self.value = value


class CtorAllowInherited(_CtorBase):
    pass
