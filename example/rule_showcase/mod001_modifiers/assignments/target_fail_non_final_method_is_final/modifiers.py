"""WithNonFinalMethod.step is decorated with @final — violates is_non_final_method."""

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
    @final
    def step(self) -> None:
        """Should not be final, but is."""
        return None
