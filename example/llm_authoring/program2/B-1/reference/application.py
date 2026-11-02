"""The application core: lending use cases, written against the ports only.

The store, the notifier and the clock are injected; nothing here knows which
adapters implement them.
"""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import (
    forbid_foreign_writes,
    forbid_imports,
    forbid_runtime_instantiation,
    require_runtime_delegation,
)

from .domain import Loan
from .ports import Clock, LoanStore, Notifier

__archtest__: Annotated[
    None,
    forbid_imports(
        "adapters_memory",
        "adapters_notify",
        "wiring",
        "api",
        scope="module",
        mode="direct",
    ),
]


class LendingService:
    def __init__(
        self, store: LoanStore, notifier: Notifier, clock: Clock, period: int = 14
    ) -> None:
        self._store = store
        self._notifier = notifier
        self._clock = clock
        self._period = period

    def lend(self, book_id: str, member: str) -> int:
        __archtest__: Annotated[
            None,
            forbid_runtime_instantiation(
                "adapters_memory",
                "adapters_notify",
                transitive=True,
                init={
                    "args": [
                        {"$new": "adapters_memory.InMemoryLoanStore"},
                        {"$new": "adapters_notify.OutboxNotifier"},
                        {"$new": "adapters_memory.FixedClock", "args": [1]},
                    ]
                },
                cases=[{"args": ["b1", "ann"]}],
            ),
            require_runtime_delegation(
                "notifier",
                member="send",
                init={
                    "args": [
                        {"$new": "adapters_memory.InMemoryLoanStore"},
                        {"$spy": "notifier"},
                        {"$new": "adapters_memory.FixedClock", "args": [1]},
                    ]
                },
                cases=[{"args": ["b1", "ann"]}],
            ),
        ]
        current = self._store.find(book_id)
        if current is not None and not current.returned:
            raise ValueError(f"{book_id} is already lent")
        loan = Loan(book_id, member, self._clock.today() + self._period)
        self._store.add(loan)
        self._notifier.send(member, f"{book_id} is due on day {loan.due}")
        return loan.due

    def give_back(self, book_id: str) -> bool:
        __archtest__: Annotated[
            None,
            forbid_runtime_instantiation(
                "adapters_memory",
                "adapters_notify",
                transitive=True,
                init={
                    "args": [
                        {"$new": "adapters_memory.InMemoryLoanStore"},
                        {"$new": "adapters_notify.OutboxNotifier"},
                        {"$new": "adapters_memory.FixedClock", "args": [1]},
                    ]
                },
                cases=[
                    {"args": ["b1"], "steps": [{"call": "lend", "args": ["b1", "ann"]}]}
                ],
            ),
            forbid_foreign_writes(
                init={
                    "args": [
                        {"$new": "adapters_memory.InMemoryLoanStore"},
                        {"$new": "adapters_notify.OutboxNotifier"},
                        {"$new": "adapters_memory.FixedClock", "args": [1]},
                    ]
                },
                cases=[
                    {"args": ["b1"], "steps": [{"call": "lend", "args": ["b1", "ann"]}]}
                ],
            ),
        ]
        loan = self._store.find(book_id)
        if loan is None or loan.returned:
            return False
        loan.close()
        return True
