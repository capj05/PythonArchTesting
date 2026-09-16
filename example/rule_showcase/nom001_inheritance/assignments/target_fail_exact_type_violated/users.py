"""Target — FAIL: Sparrow is no longer a Bird, violating exact_type(Bird)."""

from .bases import Bird, Mammal, Vehicle


class Dog(Mammal):
    pass


class Sparrow(Mammal):
    """Wrong nominal type — exact_type(Bird) requires Sparrow's type to be Bird."""


class Car(Vehicle):
    pass


class Robin(Bird):
    pass
