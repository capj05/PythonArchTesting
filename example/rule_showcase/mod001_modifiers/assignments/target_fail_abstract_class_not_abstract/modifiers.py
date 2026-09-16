"""AbstractShape is no longer abstract — violates is_abstract_class."""

from abc import ABC, abstractmethod
from typing import final


class AbstractShape:
    """Not abstract: no ABC base, no @abstractmethod."""

    pass


class ConcreteCircle:
    def area(self) -> float:
        return 0.0


@final
class FinalConfig:
    pass


class NonFinalBase:
    pass


class WithAbstractMethod(ABC):
    @abstractmethod
    def step(self) -> None: ...


class WithConcreteMethod:
    def step(self) -> None:
        return None


class WithFinalMethod:
    @final
    def step(self) -> None:
        return None


class WithNonFinalMethod:
    def step(self) -> None:
        return None
