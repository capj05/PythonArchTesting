"""Driving adapter: request handlers that talk to the application only."""

from __future__ import annotations

from typing import Annotated, Any

from pythonarchtesting.rules import (
    forbid_foreign_writes,
    forbid_imports,
    forbid_runtime_calls,
    require_runtime_calls,
)

__archtest__: Annotated[
    None,
    forbid_imports(
        "adapters_memory",
        "adapters_notify",
        "ports",
        "domain",
        "wiring",
        scope="module",
        mode="direct",
    ),
]


def lend_book(request: dict[str, Any], service: Any) -> dict[str, Any]:
    __archtest__: Annotated[
        None,
        forbid_runtime_calls(
            "adapters_memory",
            "adapters_notify",
            "ports",
            "domain",
            transitive=True,
            through=["application"],
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
                }
            ],
        ),
        require_runtime_calls(
            "application",
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
                }
            ],
        ),
        forbid_foreign_writes(
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
                }
            ],
        ),
    ]
    if not request.get("book") or not request.get("member"):
        return {"status": "error", "reason": "book and member are required"}
    due = service.lend(request["book"], request["member"])
    return {"status": "ok", "due": due}


def return_book(request: dict[str, Any], service: Any) -> dict[str, Any]:
    __archtest__: Annotated[
        None,
        forbid_runtime_calls(
            "adapters_memory",
            "adapters_notify",
            "ports",
            "domain",
            transitive=True,
            through=["application"],
            cases=[
                {
                    "args": [
                        {"book": "b1"},
                        {
                            "$new": "application.LendingService",
                            "args": [
                                {
                                    "$new": "adapters_memory.InMemoryLoanStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.Loan",
                                                "args": ["b1", "ann", 5],
                                            }
                                        ]
                                    ],
                                },
                                {"$new": "adapters_notify.OutboxNotifier"},
                                {"$new": "adapters_memory.FixedClock", "args": [1]},
                            ],
                        },
                    ]
                }
            ],
        ),
        require_runtime_calls(
            "application",
            cases=[
                {
                    "args": [
                        {"book": "b1"},
                        {
                            "$new": "application.LendingService",
                            "args": [
                                {
                                    "$new": "adapters_memory.InMemoryLoanStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.Loan",
                                                "args": ["b1", "ann", 5],
                                            }
                                        ]
                                    ],
                                },
                                {"$new": "adapters_notify.OutboxNotifier"},
                                {"$new": "adapters_memory.FixedClock", "args": [1]},
                            ],
                        },
                    ]
                }
            ],
        ),
        forbid_foreign_writes(
            cases=[
                {
                    "args": [
                        {"book": "b1"},
                        {
                            "$new": "application.LendingService",
                            "args": [
                                {
                                    "$new": "adapters_memory.InMemoryLoanStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.Loan",
                                                "args": ["b1", "ann", 5],
                                            }
                                        ]
                                    ],
                                },
                                {"$new": "adapters_notify.OutboxNotifier"},
                                {"$new": "adapters_memory.FixedClock", "args": [1]},
                            ],
                        },
                    ]
                }
            ],
        ),
    ]
    returned = service.give_back(request["book"])
    return {"status": "ok" if returned else "not_lent"}
