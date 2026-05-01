"""Storage package for the checkout assignment.

Domain code must not depend on HTTP libraries — declared via
``forbid_imports("requests", scope="package", package="storage")``.
"""

from typing import Annotated

from pythonarchtesting.rules import forbid_imports

from .repository import InMemoryOrderRepository

__archtest__: Annotated[
    None,
    forbid_imports("requests", scope="package", package="storage"),
]

__all__ = ["InMemoryOrderRepository"]
