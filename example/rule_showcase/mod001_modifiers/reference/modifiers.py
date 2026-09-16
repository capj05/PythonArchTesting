"""Reference declarations for the eight modifier markers."""

from abc import ABC, abstractmethod
from typing import Annotated, final

from pythonarchtesting.rules import (
    is_abstract_class,
    is_abstract_method,
    is_concrete_class,
    is_final_class,
    is_final_method,
    is_non_abstract_method,
    is_non_final_class,
    is_non_final_method,
)


class AbstractShape(ABC):
    """Class-level: must be abstract."""

    __archtest__: Annotated[None, is_abstract_class()]

    @abstractmethod
    def area(self) -> float: ...


class ConcreteCircle:
    """Must be concrete."""

    __archtest__: Annotated[None, is_concrete_class()]

    def area(self) -> float:
        return 0.0


@final
class FinalConfig:
    """Must be final."""

    __archtest__: Annotated[None, is_final_class()]


class NonFinalBase:
    """Must be non-final."""

    __archtest__: Annotated[None, is_non_final_class()]


class WithAbstractMethod(ABC):
    @abstractmethod
    def step(self) -> None:
        __archtest__: Annotated[None, is_abstract_method()]
        ...


class WithConcreteMethod:
    def step(self) -> None:
        __archtest__: Annotated[None, is_non_abstract_method()]
        return None


class WithFinalMethod:
    @final
    def step(self) -> None:
        __archtest__: Annotated[None, is_final_method()]
        return None


class WithNonFinalMethod:
    def step(self) -> None:
        __archtest__: Annotated[None, is_non_final_method()]
        return None
