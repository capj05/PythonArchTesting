"""Reference enum types for the ENUM001 is_enum showcase.

Each class carries a single ``is_enum`` marker. The ``_MarkerEnum`` base is
intentionally member-free so ``TransitiveEnum`` can subclass it (Python forbids
subclassing an Enum that already has members).
"""

from enum import Enum, Flag, IntEnum, StrEnum
from typing import Annotated

from pythonarchtesting.rules import is_enum


class Color(Enum):
    __archtest__: Annotated[None, is_enum()]
    RED = "red"
    BLUE = "blue"


class Priority(IntEnum):
    __archtest__: Annotated[None, is_enum()]
    LOW = 1
    HIGH = 2


class Mode(StrEnum):
    __archtest__: Annotated[None, is_enum()]
    READ = "read"
    WRITE = "write"


class Permissions(Flag):
    __archtest__: Annotated[None, is_enum()]
    READ = 1
    WRITE = 2
    EXEC = 4


class _MarkerEnum(Enum):
    """Empty Enum base — subclassable because it has no members."""


class TransitiveEnum(_MarkerEnum):
    __archtest__: Annotated[None, is_enum()]
    A = 1
    B = 2
