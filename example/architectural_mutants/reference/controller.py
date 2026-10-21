"""Presentation layer: checks the request and delegates to the service.

Intent I1 (layering): the controller talks to the service only, never to
storage. Statically, it must not import the repository; at run time, it must
call into the service, must not call into the repository, and its whole call
tree must use exactly the module-to-module calls of this reference.

The second case, an empty order, drives the early return. Without it no case
runs that line, and a layer bypass placed there (mutant M03) passes; the
coverage note in the passing results is what points at it. It is not given to
``require_runtime_calls``, which demands a call into the service in every
case, and the empty order makes none.
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
    forbid_imports("repository", scope="module", mode="reachable"),
]


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    __archtest__: Annotated[  # noqa: F842
        None,
        require_runtime_calls(
            "service",
            cases=[
                {
                    "args": [
                        {"id": "A1", "prices": [10.0, 5.5]},
                        {
                            "$new": "service.OrderService",
                            "args": [
                                {"$new": "repository.OrderRepository"},
                                {"$new": "pricing.PercentDiscount", "args": [10]},
                                {"$new": "events.EventBus"},
                            ],
                        },
                    ]
                }
            ],
        ),
        forbid_runtime_calls(
            "repository",
            cases=[
                {
                    "args": [
                        {"id": "A1", "prices": [10.0, 5.5]},
                        {
                            "$new": "service.OrderService",
                            "args": [
                                {"$new": "repository.OrderRepository"},
                                {"$new": "pricing.PercentDiscount", "args": [10]},
                                {"$new": "events.EventBus"},
                            ],
                        },
                    ]
                },
                {
                    "args": [
                        {"id": "A2", "prices": []},
                        {
                            "$new": "service.OrderService",
                            "args": [
                                {"$new": "repository.OrderRepository"},
                                {"$new": "pricing.PercentDiscount", "args": [10]},
                                {"$new": "events.EventBus"},
                            ],
                        },
                    ]
                },
            ],
        ),
        enforce_reference_calls(
            require_all=True,
            cases=[
                {
                    "args": [
                        {"id": "A1", "prices": [10.0, 5.5]},
                        {
                            "$new": "service.OrderService",
                            "args": [
                                {"$new": "repository.OrderRepository"},
                                {"$new": "pricing.PercentDiscount", "args": [10]},
                                {"$new": "events.EventBus"},
                            ],
                        },
                    ]
                },
                {
                    "args": [
                        {"id": "A2", "prices": []},
                        {
                            "$new": "service.OrderService",
                            "args": [
                                {"$new": "repository.OrderRepository"},
                                {"$new": "pricing.PercentDiscount", "args": [10]},
                                {"$new": "events.EventBus"},
                            ],
                        },
                    ]
                },
            ],
        ),
    ]
    if not request.get("prices"):
        return {"status": "error", "reason": "empty order"}
    total = service.place(request["id"], request["prices"])
    return {"status": "ok", "total": total}
