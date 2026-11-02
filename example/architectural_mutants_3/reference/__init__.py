"""Clinic appointments: book, cancel and reschedule visits, remind patients.

The program is one package in layers, each layer a subpackage: ``domain``
(patients, slots, appointments, cancellation policies, events), ``ports``
(what the application needs from the outside, as protocols), ``application``
(the use cases and the event bus), ``adapters`` (stores, notifier, clocks)
and ``api`` (request handlers). ``wiring`` composes them.
"""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import enforce_layers, forbid_cycles

__archtest__: Annotated[
    None,
    enforce_layers(
        "wiring",
        "api | adapters",
        "application",
        "ports",
        "domain",
        entry="wiring.serve",
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
            }
        ],
    ),
    forbid_cycles(
        entry="wiring.serve",
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
            }
        ],
    ),
]
