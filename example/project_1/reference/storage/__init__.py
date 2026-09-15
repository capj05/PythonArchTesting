"""Storage package used to demonstrate reachable forbidden-import checks."""

from typing import Annotated

from pythonarchtesting.rules import forbid_imports

from .repository import MemorySubmissionRepository

__archtest__: Annotated[
    None,
    forbid_imports("requests", scope="package", package="storage"),
]

__all__ = ["MemorySubmissionRepository"]
