"""Base classes used by the NOM001 inheritance showcase. No markers."""


class Animal:
    """Top-level animal base class."""


class Mammal(Animal):
    """Animal subtype used to demonstrate transitive inheritance."""


class Vehicle:
    """Unrelated base class — used by classes that must NOT be Animals."""


class Bird(Animal):
    """Animal subtype used to demonstrate exact / direct inheritance checks."""
