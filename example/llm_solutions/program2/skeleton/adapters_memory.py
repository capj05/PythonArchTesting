"""Driven adapters kept in memory: the loan store and a fixed clock."""

from __future__ import annotations
from .domain import Loan


class InMemoryLoanStore:

    def __init__(self, loans: list[Loan] | None = None) -> None:
        raise NotImplementedError

    def add(self, loan: Loan) -> None:
        raise NotImplementedError

    def find(self, book_id: str) -> Loan | None:
        raise NotImplementedError


class FixedClock:

    def __init__(self, day: int) -> None:
        raise NotImplementedError

    def today(self) -> int:
        raise NotImplementedError
