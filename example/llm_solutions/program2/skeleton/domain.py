"""The domain: a loan, which depends on nothing else in the project."""

from __future__ import annotations


class Loan:

    def __init__(self, book_id: str, member: str, due: int) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def is_overdue(self, today: int) -> bool:
        raise NotImplementedError
