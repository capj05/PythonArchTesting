"""Reference contracts for the API003 / required_attribute + required_constructor showcase.

Each class carries exactly ONE ``__archtest__`` annotation. Stacking multiple
class-level ``__archtest__`` annotations would collide on Python's
``__annotations__`` dict (later wins), so coverage is spread across multiple
classes instead.
"""

from dataclasses import dataclass
from typing import Annotated

from pythonarchtesting.rules import required_attribute, required_constructor


class HasName:
    """Instance attribute ``name: str`` must be assigned by ``__init__``."""

    __archtest__: Annotated[
        None,
        required_attribute("name", annotation=str, storage="instance"),
    ]

    def __init__(self, name: str) -> None:
        self.name: str = name


class HasVersion:
    """Class-level constant ``VERSION: str`` must exist as a class attribute."""

    __archtest__: Annotated[
        None,
        required_attribute("VERSION", annotation=str, storage="class"),
    ]

    VERSION: str = "1.0"


class HasPropertyOk:
    """``size: int`` may be implemented as a ``@property`` (allow_property=True)."""

    __archtest__: Annotated[
        None,
        required_attribute("size", annotation=int, allow_property=True),
    ]

    @property
    def size(self) -> int:
        return 0


@dataclass
class HasDataclassField:
    """Dataclass field ``count: int`` is interpreted as an attribute."""

    __archtest__: Annotated[
        None,
        required_attribute("count", annotation=int, interpret_dataclass_fields=True),
    ]

    count: int = 0


class HasCompatibleCtor:
    """Constructor must be signature-compatible with ``__init__(self, x, y)``."""

    __archtest__: Annotated[
        None,
        required_constructor(signature_mode="compatible"),
    ]

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class HasExactCtor:
    """Constructor must match ``__init__(self, x: int)`` exactly (no extras)."""

    __archtest__: Annotated[
        None,
        required_constructor(signature_mode="exact"),
    ]

    def __init__(self, x: int) -> None:
        self.x = x


class _CtorBase:
    """Base class providing a constructor for inheritance scenarios."""

    def __init__(self, value: int) -> None:
        self.value = value


class CtorAllowInherited(_CtorBase):
    """Constructor may be inherited from a base class (allow_inherited=True).

    The source class itself must still declare an ``__init__`` so the
    compiler knows the expected signature; ``allow_inherited`` only
    relaxes the **target-side** lookup so that targets without their own
    ``__init__`` can satisfy the rule via their parent's.
    """

    __archtest__: Annotated[
        None,
        required_constructor(allow_inherited=True),
    ]

    def __init__(self, value: int) -> None:
        super().__init__(value)
