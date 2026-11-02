"""Ports: what the application needs from the outside world."""

from __future__ import annotations

from typing import Protocol

from .domain import Loan


class LoanStore(Protocol):
    def add(self, loan: Loan) -> None: ...

    def find(self, book_id: str) -> Loan | None: ...


class Notifier(Protocol):
    def send(self, member: str, text: str) -> None: ...


class Clock(Protocol):
    def today(self) -> int: ...
