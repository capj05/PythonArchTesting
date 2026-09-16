"""target_fail_class_storage — HasName stores ``name`` as a class attribute."""

from dataclasses import dataclass


class HasName:
    # BUG: ``name`` is declared at class level — required storage="instance".
    name: str = "x"

    def __init__(self, name: str) -> None:
        # Note: no ``self.name = name`` assignment.
        _ = name


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
    pass
