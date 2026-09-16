"""target_fail_wrong_ctor_arity — HasExactCtor has an extra parameter (signature_mode=exact)."""

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
    # BUG: ``signature_mode="exact"`` rejects the extra ``extra`` parameter.
    def __init__(self, x: int, extra: int = 0) -> None:
        self.x = x
        self.extra = extra


class _CtorBase:
    def __init__(self, value: int) -> None:
        self.value = value


class CtorAllowInherited(_CtorBase):
    pass
