"""target_pass_inherited_ctor — CtorAllowInherited inherits __init__ from a base."""

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
    # No __init__ defined here; inherited from _CtorBase.
    # ``allow_inherited=True`` on the reference accepts this.
    pass
