"""Reference module for the API004 / required_factory showcase.

The ``required_factory`` marker MUST be placed inside the body of the
factory method (or ``__init__`` when ``satisfy_with=('constructor',)``).
Placing it as a class-body annotation produces a
``compiler_invalid_target`` warning (expected_kind=method, found_kind=class)
and the rule is silently dropped. This matches the pattern used in
``tests/unit/test_rules/test_api004_required_factory_compile.py``.
"""

from typing import Annotated

from pythonarchtesting.rules import required_factory


class ClassmethodFactory:
    """Classmethod factory matched by exact alias ``create``."""

    def __init__(self, value: int) -> None:
        self.value = value

    @classmethod
    def create(cls, value: int) -> "ClassmethodFactory":
        __archtest__: Annotated[
            None,
            required_factory(
                satisfy_with=("classmethod",),
                name_match="exact",
                aliases=("create",),
            ),
        ]
        return cls(value)


class StaticmethodFactory:
    """Staticmethod factory matched by exact alias ``build``."""

    def __init__(self, value: int) -> None:
        self.value = value

    @staticmethod
    def build(value: int) -> "StaticmethodFactory":
        __archtest__: Annotated[
            None,
            required_factory(
                satisfy_with=("staticmethod",),
                name_match="exact",
                aliases=("build",),
            ),
        ]
        return StaticmethodFactory(value)


class ConstructorOnly:
    """No explicit factory — ``satisfy_with`` includes ``constructor`` so
    the ``__init__`` itself satisfies the rule. The marker therefore lives
    in ``__init__``.
    """

    def __init__(self, x: int, y: int) -> None:
        __archtest__: Annotated[
            None,
            required_factory(satisfy_with=("constructor",)),
        ]
        self.x = x
        self.y = y


class ExtendedMatch:
    """``detection_mode='extended'`` widens the candidate set beyond strict
    ``classmethod``/``staticmethod`` shapes."""

    def __init__(self, raw: str) -> None:
        self.raw = raw

    @classmethod
    def make(cls, raw: str) -> "ExtendedMatch":
        __archtest__: Annotated[
            None,
            required_factory(
                detection_mode="extended",
                name_match="exact",
                aliases=("make",),
                satisfy_with=("classmethod",),
            ),
        ]
        return cls(raw)


class StaticAttributeFactory:
    """Factory assigned via ``make = classmethod(...)`` rather than the
    ``@classmethod`` decorator. The marker lives inside the underlying
    function body.
    """

    def __init__(self, n: int) -> None:
        self.n = n

    def _make_impl(cls, n: int) -> "StaticAttributeFactory":
        __archtest__: Annotated[
            None,
            required_factory(
                name_match="exact",
                aliases=("make",),
                satisfy_with=("classmethod",),
            ),
        ]
        return cls(n)

    make = classmethod(_make_impl)


class CheckedReturnAnnotation:
    """``return_annotation_mode='check'`` enforces the factory's return
    type matches the owning class.
    """

    def __init__(self, value: int) -> None:
        self.value = value

    @classmethod
    def create(cls, value: int) -> "CheckedReturnAnnotation":
        __archtest__: Annotated[
            None,
            required_factory(
                return_annotation_mode="exact",
                aliases=("create",),
                satisfy_with=("classmethod",),
            ),
        ]
        return cls(value)
