"""Target — PASS: Dog inherits Animal via a deeper transitive chain."""

from .bases import Bird, Mammal, Vehicle


class Canine(Mammal):
    """Extra layer between Dog and Animal."""


class Dog(Canine):
    """Subclass of Animal transitively through Canine -> Mammal -> Animal."""


class StandaloneType:
    pass


class Car(Vehicle):
    pass


class Robin(Bird):
    pass
