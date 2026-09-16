"""target_pass_property_satisfies_attr — ``HasPropertyOk.size`` stays a property."""

from dataclasses import dataclass


class HasName:
    def __init__(self, name: str) -> None:
        self.name: str = name


class HasVersion:
    VERSION: str = "1.0"


class HasPropertyOk:
    # ``allow_property=True`` on the reference accepts a @property here.
    @property
    def size(self) -> int:
        return 42


@dataclass
class HasDataclassField:
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
