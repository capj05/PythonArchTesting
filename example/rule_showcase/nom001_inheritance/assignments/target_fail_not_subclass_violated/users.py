"""Target — FAIL: Car becomes a subclass of Animal, violating not_subclass_of(Animal)."""

from .bases import Animal, Bird, Mammal


class Dog(Mammal):
    pass


class StandaloneType:
    pass


class Car(Animal):
    """Wrong base — Car must NOT be a subclass of Animal."""


class Robin(Bird):
    pass
