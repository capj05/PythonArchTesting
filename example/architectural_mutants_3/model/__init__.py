"""Reference for the model mode of the third architectural-mutant evaluation.

``run.py`` puts this file next to a copy of ``../solution`` and uses the
result as the reference: the solution with no marker but this one, which
runs the composition root on a sequence of requests (booking, a taken slot,
moving, free slots, reminders, a late and an early cancellation), once on
the in-memory store and once on SQLite.
"""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import architecture_entry

__archtest__: Annotated[
    None,
    architecture_entry(
        entry="wiring.serve",
        require_all=True,
        cases=[
            {
                "args": [
                    [
                        {
                            "action": "book",
                            "patient": "P1",
                            "name": "Ann Lee",
                            "email": "ann@example.org",
                            "doctor": "novak",
                            "day": 2,
                            "hour": 9,
                        },
                        {
                            "action": "book",
                            "patient": "P2",
                            "name": "Bo Ek",
                            "email": "bo@example.org",
                            "doctor": "novak",
                            "day": 2,
                            "hour": 9,
                        },
                        {
                            "action": "book",
                            "patient": "P2",
                            "name": "Bo Ek",
                            "email": "bo@example.org",
                            "doctor": "novak",
                            "day": 1,
                            "hour": 10,
                        },
                        {"action": "move", "appointment": "A1", "day": 2, "hour": 10},
                        {"action": "free", "doctor": "novak", "day": 2},
                        {"action": "remind", "day": 2},
                        {"action": "cancel", "appointment": "A2"},
                        {"action": "cancel", "appointment": "A1"},
                        {"action": "pay", "appointment": "A1"},
                    ]
                ]
            },
            {
                "args": [
                    [
                        {
                            "action": "book",
                            "patient": "P1",
                            "name": "Ann Lee",
                            "email": "ann@example.org",
                            "doctor": "novak",
                            "day": 2,
                            "hour": 9,
                        },
                        {
                            "action": "book",
                            "patient": "P2",
                            "name": "Bo Ek",
                            "email": "bo@example.org",
                            "doctor": "novak",
                            "day": 2,
                            "hour": 9,
                        },
                        {
                            "action": "book",
                            "patient": "P2",
                            "name": "Bo Ek",
                            "email": "bo@example.org",
                            "doctor": "novak",
                            "day": 1,
                            "hour": 10,
                        },
                        {"action": "move", "appointment": "A1", "day": 2, "hour": 10},
                        {"action": "free", "doctor": "novak", "day": 2},
                        {"action": "remind", "day": 2},
                        {"action": "cancel", "appointment": "A2"},
                        {"action": "cancel", "appointment": "A1"},
                        {"action": "pay", "appointment": "A1"},
                    ]
                ],
                "kwargs": {"sqlite": True},
            },
        ],
    ),
]
