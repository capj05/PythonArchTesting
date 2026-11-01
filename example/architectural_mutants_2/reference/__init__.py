"""Reference for the second architectural-mutant evaluation.

The same code as ``../solution``, plus the markers that state its
ports-and-adapters architecture. Where a static marker can express an intent,
both the static and the runtime marker are declared.

The markers here state intents of the whole program as one layer order (H7):
the composition root on top; the driving adapter (``api``) and the driven
adapters side by side and independent of each other; then the application,
the ports and the domain. The application calls the driven adapters at run
time through the ports it was given, which the reference does too, so only
calls against the order that the reference does not make count. No two
modules may depend on each other either (H8). Both are checked on every
import, and on the calls made while a handler lends a book (and rejects an
incomplete request).
"""

from __future__ import annotations

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
    forbid_cycles(
        entry="api.lend_book",
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
