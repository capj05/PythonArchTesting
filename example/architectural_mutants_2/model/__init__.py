"""Reference for the model mode of the second architectural-mutant evaluation.

``run.py`` puts this file next to a copy of ``../solution`` and uses the
result as the reference: the solution with no marker but this one, which
says which handler to run, and on which requests.
"""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import architecture_entry

__archtest__: Annotated[
    None,
    architecture_entry(
        entry="api.lend_book",
        require_all=True,
        cases=[
            {
                "args": [
                    {"book": "B1", "member": "ann"},
                    {
                        "$new": "application.LendingService",
                        "args": [
                            {"$new": "adapters_memory.InMemoryLoanStore"},
                            {"$new": "adapters_notify.OutboxNotifier"},
                            {"$new": "adapters_memory.FixedClock", "args": [3]},
                        ],
                    },
                ]
            },
            {
                "args": [
                    {"book": "B1"},
                    {
                        "$new": "application.LendingService",
                        "args": [
                            {"$new": "adapters_memory.InMemoryLoanStore"},
                            {"$new": "adapters_notify.OutboxNotifier"},
                            {"$new": "adapters_memory.FixedClock", "args": [3]},
                        ],
                    },
                ]
            },
        ],
    ),
]
