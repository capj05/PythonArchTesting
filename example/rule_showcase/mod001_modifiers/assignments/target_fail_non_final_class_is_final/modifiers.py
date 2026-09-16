"""NonFinalBase is decorated with @final — violates is_non_final_class."""

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


@final
class NonFinalBase:
    """Should not be final, but is."""

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
