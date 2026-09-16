"""Target — FAIL: Robin inherits from Bird only transitively (via Sparrow)."""

from .bases import Bird, Mammal, Vehicle


class Dog(Mammal):
    pass


class StandaloneType:
    pass


class Car(Vehicle):
    pass


class Robin(Sparrow):
    """Wrong direct base — Robin must inherit DIRECTLY from Bird, not via Sparrow."""
