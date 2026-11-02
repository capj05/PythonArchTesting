"""Reference for the architectural-mutant evaluation.

The same code as ``../solution``, plus the markers that state its
architecture. Where a static marker can express an intent, both the static
and the runtime marker are declared, so the evaluation can tell which kind of
check catches which seeded violation.

The markers here state intents of the whole program. I1 (layering) as one
layer order: the controller on top, the service below it, the
infrastructure modules side by side below the service, the domain at the
bottom; the service is closed, so nothing above it reaches past it. I8: no
two modules depend on each other. Both are checked on every import, and on
the calls made while the controller handles an order and an empty order.
"""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import enforce_layers, forbid_cycles

__archtest__: Annotated[
    None,
    enforce_layers(
        "controller",
        "service",
        "repository | pricing | events | config",
        "models",
        closed=["service"],
        entry="controller.handle_order",
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
    forbid_cycles(
        entry="controller.handle_order",
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
