"""The application core: lending use cases, written against the ports only.

The store, the notifier and the clock are injected; nothing here knows which
adapters implement them.
"""

from __future__ import annotations
from .domain import Loan
from .ports import Clock, LoanStore, Notifier


class LendingService:

    def __init__(
        self, store: LoanStore, notifier: Notifier, clock: Clock, period: int = 14
    ) -> None:
        raise NotImplementedError

    def lend(self, book_id: str, member: str) -> int:
        raise NotImplementedError

    def give_back(self, book_id: str) -> bool:
        raise NotImplementedError
