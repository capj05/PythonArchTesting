"""Reference classes for the API005 / require_method_set showcase.

Each class carries exactly one ``require_method_set`` marker via
``__archtest__`` to isolate one parameter combination at a time.
"""

from typing import Annotated

from pythonarchtesting.rules import require_method_set


class HandlerSet:
    """At least 2 (and at most 5) ``handle_*`` methods."""

    __archtest__: Annotated[
        None,
        require_method_set(
            name_match="regex",
            pattern=r"^handle_.*$",
            min_count=2,
            max_count=5,
        ),
    ]

    def handle_create(self) -> None:
        return None

    def handle_update(self) -> None:
        return None

    def handle_delete(self) -> None:
        return None


class AliasMethods:
    """Exactly one alias from ``validate``/``check``/``verify`` must exist."""

    __archtest__: Annotated[
        None,
        require_method_set(
            name_match="names",
            names=["validate", "check", "verify"],
            min_count=1,
            max_count=1,
        ),
    ]

    def validate(self) -> bool:
        return True


class ClassmethodFactories:
    """At least one classmethod-kind factory named ``create``/``build``/``make``."""

    __archtest__: Annotated[
        None,
        require_method_set(
            name_match="names",
            names=["create", "build", "make"],
            method_kind="classmethod",
            min_count=1,
        ),
    ]

    @classmethod
    def create(cls) -> "ClassmethodFactories":
        return cls()


class DeclaredHandlers:
    """``process_*`` methods must be declared on the class itself."""

    __archtest__: Annotated[
        None,
        require_method_set(
            name_match="regex",
            pattern=r"^process_.*$",
            declared_only=True,
            min_count=2,
        ),
    ]

    def process_a(self) -> None:
        return None

    def process_b(self) -> None:
        return None
