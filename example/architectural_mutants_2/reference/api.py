"""Driving adapter: request handlers that talk to the application only.

Intent H4 (driving adapter): the handlers talk to the application, never to
the driven adapters or the domain directly. Statically, the module must not
import them; at run time, a handler must call into the application, must not
call into the adapters or the domain unless through the application (a detour
through a helper module of the target's own counts), and its call tree must
keep the module-to-module calls of this reference.

Each handler has a case for its early exit as well, so a bypass placed there
runs.
"""

from __future__ import annotations

from typing import Annotated, Any

from pythonarchtesting.rules import (
    enforce_reference_calls,
    forbid_imports,
    forbid_runtime_calls,
    require_runtime_calls,
)

__archtest__: Annotated[
    None,
    forbid_imports(
        "adapters_memory",
        "adapters_notify",
        "domain",
        "wiring",
        scope="module",
        mode="reachable",
    ),
]


def lend_book(request: dict[str, Any], service: Any) -> dict[str, Any]:
    __archtest__: Annotated[  # noqa: F842
        None,
        require_runtime_calls(
            "application",
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
                }
            ],
        ),
        forbid_runtime_calls(
            "adapters_memory",
            "adapters_notify",
            "domain",
            transitive=True,
            through=["application"],
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
        enforce_reference_calls(
            require_all=True,
            allow_new_modules=True,
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
    if not request.get("book") or not request.get("member"):
        return {"status": "error", "reason": "book and member are required"}
    due = service.lend(request["book"], request["member"])
    return {"status": "ok", "due": due}


def return_book(request: dict[str, Any], service: Any) -> dict[str, Any]:
    __archtest__: Annotated[  # noqa: F842
        None,
        require_runtime_calls(
            "application",
            cases=[
                {
                    "args": [
                        {"book": "B1"},
                        {
                            "$new": "application.LendingService",
                            "args": [
                                {
                                    "$new": "adapters_memory.InMemoryLoanStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.Loan",
                                                "args": ["B1", "ann", 17],
                                            }
                                        ]
                                    ],
                                },
                                {"$new": "adapters_notify.OutboxNotifier"},
                                {"$new": "adapters_memory.FixedClock", "args": [3]},
                            ],
                        },
                    ]
                },
                {
                    "args": [
                        {"book": "B2"},
                        {
                            "$new": "application.LendingService",
                            "args": [
                                {
                                    "$new": "adapters_memory.InMemoryLoanStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.Loan",
                                                "args": ["B1", "ann", 17],
                                            }
                                        ]
                                    ],
                                },
                                {"$new": "adapters_notify.OutboxNotifier"},
                                {"$new": "adapters_memory.FixedClock", "args": [3]},
                            ],
                        },
                    ]
                },
            ],
        ),
        forbid_runtime_calls(
            "adapters_memory",
            "adapters_notify",
            "domain",
            transitive=True,
            through=["application"],
            cases=[
                {
                    "args": [
                        {"book": "B1"},
                        {
                            "$new": "application.LendingService",
                            "args": [
                                {
                                    "$new": "adapters_memory.InMemoryLoanStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.Loan",
                                                "args": ["B1", "ann", 17],
                                            }
                                        ]
                                    ],
                                },
                                {"$new": "adapters_notify.OutboxNotifier"},
                                {"$new": "adapters_memory.FixedClock", "args": [3]},
                            ],
                        },
                    ]
                },
                {
                    "args": [
                        {"book": "B2"},
                        {
                            "$new": "application.LendingService",
                            "args": [
                                {
                                    "$new": "adapters_memory.InMemoryLoanStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.Loan",
                                                "args": ["B1", "ann", 17],
                                            }
                                        ]
                                    ],
                                },
                                {"$new": "adapters_notify.OutboxNotifier"},
                                {"$new": "adapters_memory.FixedClock", "args": [3]},
                            ],
                        },
                    ]
                },
            ],
        ),
        enforce_reference_calls(
            require_all=True,
            allow_new_modules=True,
            cases=[
                {
                    "args": [
                        {"book": "B1"},
                        {
                            "$new": "application.LendingService",
                            "args": [
                                {
                                    "$new": "adapters_memory.InMemoryLoanStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.Loan",
                                                "args": ["B1", "ann", 17],
                                            }
                                        ]
                                    ],
                                },
                                {"$new": "adapters_notify.OutboxNotifier"},
                                {"$new": "adapters_memory.FixedClock", "args": [3]},
                            ],
                        },
                    ]
                },
                {
                    "args": [
                        {"book": "B2"},
                        {
                            "$new": "application.LendingService",
                            "args": [
                                {
                                    "$new": "adapters_memory.InMemoryLoanStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.Loan",
                                                "args": ["B1", "ann", 17],
                                            }
                                        ]
                                    ],
                                },
                                {"$new": "adapters_notify.OutboxNotifier"},
                                {"$new": "adapters_memory.FixedClock", "args": [3]},
                            ],
                        },
                    ]
                },
            ],
        ),
    ]
    returned = service.give_back(request["book"])
    return {"status": "ok" if returned else "not_lent"}
