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
        self._store = store
        self._notifier = notifier
        self._clock = clock
        self._period = period

    def lend(self, book_id: str, member: str) -> int:
        current = self._store.find(book_id)
        if current is not None and not current.returned:
            raise ValueError(f"{book_id} is already lent")
        loan = Loan(book_id, member, self._clock.today() + self._period)
        self._store.add(loan)
        self._notifier.send(member, f"{book_id} is due on day {loan.due}")
        return loan.due

    def give_back(self, book_id: str) -> bool:
        loan = self._store.find(book_id)
        if loan is None or loan.returned:
            return False
        loan.close()
        return True
