"""Reference class for the required_method showcase.

Each method on ``Service`` carries an ``__archtest__`` annotation that pins
a different combination of ``required_method`` parameters so targets can
demonstrate the verdict for one specific concern at a time. Method bodies
are trivial -- only the *declaration* and *signature* are checked.
"""

from typing import Annotated

from pythonarchtesting.rules import required_method


class Service:
    """Reference contract for the required_method showcase."""

    def process(self, payload: dict) -> bool:
        __archtest__: Annotated[None, required_method()]  # noqa: F841
        return bool(payload)

    def validate(self, value: str) -> bool:
        __archtest__: Annotated[  # noqa: F841
            None,
            required_method(
                name_match="alias",
                aliases=["validate", "check", "verify"],
            ),
        ]
        return bool(value)

    def compute(self, x: int, y: int) -> int:
        __archtest__: Annotated[  # noqa: F841
            None,
            required_method(signature_mode="compatible"),
        ]
        return x + y

    def count_items(self) -> int:
        __archtest__: Annotated[  # noqa: F841
            None,
            required_method(enforce_method_kind=True),
        ]
        return 0

    def helper(self) -> None:
        __archtest__: Annotated[  # noqa: F841
            None,
            required_method(declared_only=False),
        ]
        return None

    def internal_check(self) -> None:
        __archtest__: Annotated[  # noqa: F841
            None,
            required_method(declared_only=True),
        ]
        return None

    def optional_hook(self) -> None:
        __archtest__: Annotated[  # noqa: F841
            None,
            required_method(allow_missing=True),
        ]
        return None
