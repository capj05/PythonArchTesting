"""The domain: a loan, which depends on nothing else in the project.

Intent H1 (independent domain): the module imports no other project module
except through ``TYPE_CHECKING``, not even inside a function. At run time the
calls of the use cases (``api``) must keep the reference's module graph, in
which the domain calls nobody.
"""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import forbid_imports

__archtest__: Annotated[
    None,
    forbid_imports(
        "application",
        "ports",
        "adapters_memory",
        "adapters_notify",
        "api",
        "wiring",
        scope="module",
        mode="direct",
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
