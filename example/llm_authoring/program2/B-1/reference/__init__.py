"""A small library-loans service in ports-and-adapters style."""

from typing import Annotated

from pythonarchtesting.rules import enforce_layers, forbid_cycles

__archtest__: Annotated[
    None,
    enforce_layers(
        "wiring",
        "api | adapters_memory | adapters_notify",
        "application",
        "ports",
        "domain",
        entry="api.lend_book",
        cases=[
            {
                "args": [
                    {"book": "b1", "member": "ann"},
                    {
                        "$new": "application.LendingService",
                        "args": [
                            {"$new": "adapters_memory.InMemoryLoanStore"},
                            {"$new": "adapters_notify.OutboxNotifier"},
                            {"$new": "adapters_memory.FixedClock", "args": [1]},
                        ],
                    },
                ]
            },
        ],
    ),
]

__archtest_cycles__: Annotated[
    None,
    forbid_cycles(
        entry="api.lend_book",
        cases=[
            {
                "args": [
                    {"book": "b1", "member": "ann"},
                    {
                        "$new": "application.LendingService",
                        "args": [
                            {"$new": "adapters_memory.InMemoryLoanStore"},
                            {"$new": "adapters_notify.OutboxNotifier"},
                            {"$new": "adapters_memory.FixedClock", "args": [1]},
                        ],
                    },
                ]
            },
        ],
    ),
]
