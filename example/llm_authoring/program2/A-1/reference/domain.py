"""The domain: a loan, which depends on nothing else in the project."""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import forbid_imports

__archtest__: Annotated[
    None,
    forbid_imports(
        "reference.ports",
        "reference.application",
        "reference.api",
        "reference.wiring",
        "reference.adapters_memory",
        "reference.adapters_notify",
        scope="module",
        mode="reachable",
    ),
]


class Loan:
    def __init__(self, book_id: str, member: str, due: int) -> None:
        self.book_id = book_id
        self.member = member
        self.due = due
        self.returned = False

    def close(self) -> None:
        self.returned = True

    def is_overdue(self, today: int) -> bool:
        return not self.returned and today > self.due
