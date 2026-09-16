"""Reference classes carrying nominal inheritance markers — one marker per class.

Base names are passed as **strings** (qualified or bare). The compiler resolves
them against the source project's class table — passing a Python type instead
emits a ``compiler_invalid_base_reference`` warning and the rule is dropped.
"""

from typing import Annotated

from pythonarchtesting.rules import (
    exact_type,
    inherits_directly_from,
    not_subclass_of,
    subclass_of,
)

from .bases import Animal, Bird, Mammal, Vehicle  # noqa: F401  (kept for runtime inheritance)


class Dog(Mammal):
    """Subclass of Animal (transitively, via Mammal)."""

    __archtest__: Annotated[None, subclass_of("Animal")]


class StandaloneType:
    """``exact_type`` semantics: the class must be exactly the named type
    in the target — i.e. the matched target entity equals the matched
    target counterpart of the named base. Practically this means the
    target class must be the same class (no subclassing/aliasing).

    Note: ``exact_type("Foo")`` on a class that *inherits* from Foo
    cannot pass (the rule entity ≠ the Foo entity). To use exact_type
    for genuine pass cases, attach it to a class whose name matches the
    base argument (i.e. the rule is "this class must equal itself in
    target", which forbids subclass substitutions in the target).
    """

    __archtest__: Annotated[None, exact_type("StandaloneType")]


class Car(Vehicle):
    """Must NOT be a subclass of Animal."""

    __archtest__: Annotated[None, not_subclass_of("Animal")]


class Robin(Bird):
    """Must inherit directly from Bird (not transitively)."""

    __archtest__: Annotated[None, inherits_directly_from("Bird")]
