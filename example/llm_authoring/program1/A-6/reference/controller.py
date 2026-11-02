"""Presentation layer: checks the request and delegates to the service."""

from __future__ import annotations

from typing import Annotated, Any

from pythonarchtesting.rules import forbid_imports, forbid_runtime_calls

__archtest__: Annotated[
    None,
    forbid_imports("repository", "sqlite3", "pickle", scope="module", mode="direct"),
]


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    __archtest__: Annotated[
        None,
        forbid_runtime_calls(
            "repository",
            transitive=True,
            through=["service"],
            cases=[{"args": [{"id": "A1", "prices": [10.0, 5.5]}, {"$new": "service.OrderService", "args": [{"$new": "repository.OrderRepository"}, {"$new": "pricing.PercentDiscount", "args": [10]}, {"$new": "events.EventBus"}]}]}, {"args": [{"id": "A2", "prices": []}, {"$new": "service.OrderService", "args": [{"$new": "repository.OrderRepository"}, {"$new": "pricing.PercentDiscount", "args": [10]}, {"$new": "events.EventBus"}]}]}],
        ),
    ]
    if not request.get("prices"):
        return {"status": "error", "reason": "empty order"}
    total = service.place(request["id"], request["prices"])
    return {"status": "ok", "total": total}
