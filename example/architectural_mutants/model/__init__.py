"""Reference for the model mode of the architectural-mutant evaluation.

``run.py`` puts this file next to a copy of ``../solution`` and uses the
result as the reference: the solution with no marker but this one. The
reference itself is the model of the architecture; the declaration only says
which function to run, and on which cases, to see what it does at run time.
``require_all`` makes a call between modules the reference makes and the
target skips a violation too.
"""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import architecture_entry

__archtest__: Annotated[
    None,
    architecture_entry(
        entry="controller.handle_order",
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
