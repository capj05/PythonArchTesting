"""FinalConfig is missing @final — violates is_final_class."""

from abc import ABC, abstractmethod
from typing import final


class AbstractShape(ABC):
    @abstractmethod
    def area(self) -> float: ...


class ConcreteCircle:
    def area(self) -> float:
        return 0.0


class FinalConfig:
    """No @final decorator."""

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
