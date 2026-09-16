"""Target — FAIL: Dog inherits from Vehicle, violating subclass_of(Animal)."""

from .bases import Bird, Vehicle


class Dog(Vehicle):
    """Wrong base — Dog should be a subclass of Animal, not Vehicle."""


class StandaloneType:
    pass


class Car(Vehicle):
    pass


class Robin(Bird):
    pass
