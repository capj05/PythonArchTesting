"""Target — verbatim PASS scenario."""

from .bases import Bird, Mammal, Vehicle


class Dog(Mammal):
    pass


class StandaloneType:
    pass


class Car(Vehicle):
    pass


class Robin(Bird):
    pass
