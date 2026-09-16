"""target_fail_wrong_attr_annotation — HasVersion declares ``VERSION: int`` not str."""

from dataclasses import dataclass


class HasName:
    def __init__(self, name: str) -> None:
        self.name: str = name


class HasVersion:
    # BUG: annotation is ``int`` but the rule requires ``str``.
    VERSION: int = 1


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
    pass
