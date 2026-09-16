"""WithAbstractMethod.step is concrete — violates is_abstract_method."""

from abc import ABC, abstractmethod
from typing import final


class AbstractShape(ABC):
    @abstractmethod
    def area(self) -> float: ...


class ConcreteCircle:
    def area(self) -> float:
        return 0.0


@final
class FinalConfig:
    pass


class NonFinalBase:
    pass


class WithAbstractMethod(ABC):
    def step(self) -> None:
        """No @abstractmethod — has a real body."""
        return None


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
