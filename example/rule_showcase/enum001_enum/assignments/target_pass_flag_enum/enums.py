from enum import Enum, Flag, IntEnum, StrEnum


class Color(Enum):
    RED = "red"
    BLUE = "blue"


class Priority(IntEnum):
    LOW = 1
    HIGH = 2


class Mode(StrEnum):
    READ = "read"
    WRITE = "write"


class Permissions(Flag):
    READ = 1
    WRITE = 2
    EXEC = 4


class _MarkerEnum(Enum):
    """Empty Enum base — subclassable because it has no members."""


class TransitiveEnum(_MarkerEnum):
    A = 1
    B = 2
