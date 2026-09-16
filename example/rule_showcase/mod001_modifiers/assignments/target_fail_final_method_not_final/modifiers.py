"""WithFinalMethod.step is missing @final — violates is_final_method."""

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
    def step(self) -> None:
        """No @final decorator."""
        return None


class WithNonFinalMethod:
    def step(self) -> None:
        return None
