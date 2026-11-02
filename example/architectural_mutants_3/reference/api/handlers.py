"""Request handlers: they talk to the booking service only."""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import (
    forbid_runtime_calls,
    forbid_runtime_instantiation,
    require_runtime_calls,
)

from typing import Any

from ..application.booking import BookingError, BookingService, summary
from ..application.reminders import ReminderService
from .serializers import RequestError, as_int, error, ok, require


def book(request: dict[str, Any], service: BookingService) -> dict[str, Any]:
    __archtest__: Annotated[  # noqa: F842
        None,
        require_runtime_calls(
            "application",
            cases=[
                {
                    "args": [
                        {
                            "patient": "P1",
                            "name": "Ann Lee",
                            "email": "ann@example.org",
                            "doctor": "novak",
                            "day": 2,
                            "hour": 9,
                        },
                        {
                            "$new": "application.booking.BookingService",
                            "args": [
                                {
                                    "$new": "adapters.memory_store.InMemoryAppointmentStore"
                                },
                                {
                                    "$new": "adapters.memory_store.InMemoryPatientStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.patients.Patient",
                                                "args": [
                                                    "P1",
                                                    "Ann Lee",
                                                    "ann@example.org",
                                                ],
                                            }
                                        ]
                                    ],
                                },
                                {
                                    "$new": "adapters.system_clock.FixedClock",
                                    "args": [1, 8],
                                },
                                {
                                    "$new": "domain.policies.LateCancellationFee",
                                    "args": [24, 30],
                                },
                                {"$new": "application.bus.EventBus"},
                            ],
                        },
                    ]
                }
            ],
        ),
        forbid_runtime_calls(
            "adapters",
            "domain",
            "ports",
            transitive=True,
            through=["application"],
            cases=[
                {
                    "args": [
                        {
                            "patient": "P1",
                            "name": "Ann Lee",
                            "email": "ann@example.org",
                            "doctor": "novak",
                            "day": 2,
                            "hour": 9,
                        },
                        {
                            "$new": "application.booking.BookingService",
                            "args": [
                                {
                                    "$new": "adapters.memory_store.InMemoryAppointmentStore"
                                },
                                {
                                    "$new": "adapters.memory_store.InMemoryPatientStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.patients.Patient",
                                                "args": [
                                                    "P1",
                                                    "Ann Lee",
                                                    "ann@example.org",
                                                ],
                                            }
                                        ]
                                    ],
                                },
                                {
                                    "$new": "adapters.system_clock.FixedClock",
                                    "args": [1, 8],
                                },
                                {
                                    "$new": "domain.policies.LateCancellationFee",
                                    "args": [24, 30],
                                },
                                {"$new": "application.bus.EventBus"},
                            ],
                        },
                    ]
                },
                {
                    "args": [
                        {"patient": "P1"},
                        {
                            "$new": "application.booking.BookingService",
                            "args": [
                                {
                                    "$new": "adapters.memory_store.InMemoryAppointmentStore"
                                },
                                {
                                    "$new": "adapters.memory_store.InMemoryPatientStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.patients.Patient",
                                                "args": [
                                                    "P1",
                                                    "Ann Lee",
                                                    "ann@example.org",
                                                ],
                                            }
                                        ]
                                    ],
                                },
                                {
                                    "$new": "adapters.system_clock.FixedClock",
                                    "args": [1, 8],
                                },
                                {
                                    "$new": "domain.policies.LateCancellationFee",
                                    "args": [24, 30],
                                },
                                {"$new": "application.bus.EventBus"},
                            ],
                        },
                    ]
                },
            ],
        ),
        forbid_runtime_instantiation(
            "adapters",
            cases=[
                {
                    "args": [
                        {
                            "patient": "P1",
                            "name": "Ann Lee",
                            "email": "ann@example.org",
                            "doctor": "novak",
                            "day": 2,
                            "hour": 9,
                        },
                        {
                            "$new": "application.booking.BookingService",
                            "args": [
                                {
                                    "$new": "adapters.memory_store.InMemoryAppointmentStore"
                                },
                                {
                                    "$new": "adapters.memory_store.InMemoryPatientStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.patients.Patient",
                                                "args": [
                                                    "P1",
                                                    "Ann Lee",
                                                    "ann@example.org",
                                                ],
                                            }
                                        ]
                                    ],
                                },
                                {
                                    "$new": "adapters.system_clock.FixedClock",
                                    "args": [1, 8],
                                },
                                {
                                    "$new": "domain.policies.LateCancellationFee",
                                    "args": [24, 30],
                                },
                                {"$new": "application.bus.EventBus"},
                            ],
                        },
                    ]
                },
                {
                    "args": [
                        {"patient": "P1"},
                        {
                            "$new": "application.booking.BookingService",
                            "args": [
                                {
                                    "$new": "adapters.memory_store.InMemoryAppointmentStore"
                                },
                                {
                                    "$new": "adapters.memory_store.InMemoryPatientStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.patients.Patient",
                                                "args": [
                                                    "P1",
                                                    "Ann Lee",
                                                    "ann@example.org",
                                                ],
                                            }
                                        ]
                                    ],
                                },
                                {
                                    "$new": "adapters.system_clock.FixedClock",
                                    "args": [1, 8],
                                },
                                {
                                    "$new": "domain.policies.LateCancellationFee",
                                    "args": [24, 30],
                                },
                                {"$new": "application.bus.EventBus"},
                            ],
                        },
                    ]
                },
            ],
        ),
    ]
    try:
        patient_id, name, email, doctor = require(
            request, "patient", "name", "email", "doctor"
        )
        day = as_int(request.get("day"), "day")
        hour = as_int(request.get("hour"), "hour")
        service.register(patient_id, name, email)
        appointment = service.book(patient_id, doctor, day, hour)
    except (RequestError, BookingError, ValueError) as exc:
        return error(str(exc))
    return ok(appointment=summary(appointment))


def cancel(request: dict[str, Any], service: BookingService) -> dict[str, Any]:
    __archtest__: Annotated[  # noqa: F842
        None,
        require_runtime_calls(
            "application",
            cases=[
                {
                    "args": [
                        {"appointment": "A9"},
                        {
                            "$new": "application.booking.BookingService",
                            "args": [
                                {
                                    "$new": "adapters.memory_store.InMemoryAppointmentStore"
                                },
                                {
                                    "$new": "adapters.memory_store.InMemoryPatientStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.patients.Patient",
                                                "args": [
                                                    "P1",
                                                    "Ann Lee",
                                                    "ann@example.org",
                                                ],
                                            }
                                        ]
                                    ],
                                },
                                {
                                    "$new": "adapters.system_clock.FixedClock",
                                    "args": [1, 8],
                                },
                                {
                                    "$new": "domain.policies.LateCancellationFee",
                                    "args": [24, 30],
                                },
                                {"$new": "application.bus.EventBus"},
                            ],
                        },
                    ]
                }
            ],
        ),
        forbid_runtime_calls(
            "adapters",
            "domain",
            "ports",
            transitive=True,
            through=["application"],
            cases=[
                {
                    "args": [
                        {"appointment": "A9"},
                        {
                            "$new": "application.booking.BookingService",
                            "args": [
                                {
                                    "$new": "adapters.memory_store.InMemoryAppointmentStore"
                                },
                                {
                                    "$new": "adapters.memory_store.InMemoryPatientStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.patients.Patient",
                                                "args": [
                                                    "P1",
                                                    "Ann Lee",
                                                    "ann@example.org",
                                                ],
                                            }
                                        ]
                                    ],
                                },
                                {
                                    "$new": "adapters.system_clock.FixedClock",
                                    "args": [1, 8],
                                },
                                {
                                    "$new": "domain.policies.LateCancellationFee",
                                    "args": [24, 30],
                                },
                                {"$new": "application.bus.EventBus"},
                            ],
                        },
                    ]
                },
                {
                    "args": [
                        {},
                        {
                            "$new": "application.booking.BookingService",
                            "args": [
                                {
                                    "$new": "adapters.memory_store.InMemoryAppointmentStore"
                                },
                                {
                                    "$new": "adapters.memory_store.InMemoryPatientStore",
                                    "args": [
                                        [
                                            {
                                                "$new": "domain.patients.Patient",
                                                "args": [
                                                    "P1",
                                                    "Ann Lee",
                                                    "ann@example.org",
                                                ],
                                            }
                                        ]
                                    ],
                                },
                                {
                                    "$new": "adapters.system_clock.FixedClock",
                                    "args": [1, 8],
                                },
                                {
                                    "$new": "domain.policies.LateCancellationFee",
                                    "args": [24, 30],
                                },
                                {"$new": "application.bus.EventBus"},
                            ],
                        },
                    ]
                },
            ],
        ),
    ]
    try:
        (appointment_id,) = require(request, "appointment")
        fee = service.cancel(appointment_id)
    except (RequestError, BookingError, ValueError) as exc:
        return error(str(exc))
    return ok(fee=fee)


def move(request: dict[str, Any], service: BookingService) -> dict[str, Any]:
    try:
        (appointment_id,) = require(request, "appointment")
        day = as_int(request.get("day"), "day")
        hour = as_int(request.get("hour"), "hour")
        appointment = service.move(appointment_id, day, hour)
    except (RequestError, BookingError, ValueError) as exc:
        return error(str(exc))
    return ok(appointment=summary(appointment))


def free(request: dict[str, Any], service: BookingService) -> dict[str, Any]:
    try:
        (doctor,) = require(request, "doctor")
        day = as_int(request.get("day"), "day")
        slots = service.free(doctor, day)
    except (RequestError, BookingError, ValueError) as exc:
        return error(str(exc))
    return ok(hours=[slot.hour for slot in slots])


def remind(request: dict[str, Any], reminders: ReminderService) -> dict[str, Any]:
    try:
        day = as_int(request.get("day"), "day")
    except RequestError as exc:
        return error(str(exc))
    return ok(sent=reminders.run_for(day))
