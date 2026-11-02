"""Driven adapters kept in memory: the loan store and a fixed clock."""

from __future__ import annotations

from .domain import Loan


class InMemoryLoanStore:
    def __init__(self, loans: list[Loan] | None = None) -> None:
        self._loans = {loan.book_id: loan for loan in loans or []}

    def add(self, loan: Loan) -> None:
        self._loans[loan.book_id] = loan

    def find(self, book_id: str) -> Loan | None:
        return self._loans.get(book_id)


class FixedClock:
    def __init__(self, day: int) -> None:
        self._day = day

    def today(self) -> int:
        return self._day
