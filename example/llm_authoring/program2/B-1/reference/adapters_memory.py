"""Driven adapters kept in memory: the loan store and a fixed clock."""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import implements_protocol, implements_runtime_protocol

from .domain import Loan
from .ports import Clock, LoanStore


class InMemoryLoanStore:
    __archtest__: Annotated[
        None,
        implements_protocol(LoanStore),
        implements_runtime_protocol(LoanStore, cases=[{"args": []}]),
    ]

    def __init__(self, loans: list[Loan] | None = None) -> None:
        self._loans = {loan.book_id: loan for loan in loans or []}

    def add(self, loan: Loan) -> None:
        self._loans[loan.book_id] = loan

    def find(self, book_id: str) -> Loan | None:
        return self._loans.get(book_id)


class FixedClock:
    __archtest__: Annotated[
        None,
        implements_protocol(Clock),
        implements_runtime_protocol(Clock, cases=[{"args": [1]}]),
    ]

    def __init__(self, day: int) -> None:
        self._day = day

    def today(self) -> int:
        return self._day
