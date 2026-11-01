"""Order shop: the correct solution the architectural mutants are seeded into."""

from typing import Annotated

from pythonarchtesting.rules import architecture_entry, enforce_layers, forbid_cycles

__archtest__: Annotated[
    None,
    enforce_layers(
        "controller",
        "service",
        "repository | pricing | events",
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
            }
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
            }
        ],
    ),
    architecture_entry(
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
            }
        ],
    ),
]
