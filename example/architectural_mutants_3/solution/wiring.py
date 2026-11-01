"""The composition root: the only place that chooses and builds adapters."""

from __future__ import annotations

from typing import Any

from .adapters.email_notifier import OutboxNotifier
from .adapters.memory_store import InMemoryAppointmentStore, InMemoryPatientStore
from .adapters.sqlite_store import SqliteAppointmentStore
from .adapters.system_clock import FixedClock
from .api import handlers
from .application.booking import BookingService
from .application.bus import EventBus
from .application.reminders import ReminderService
from .domain.policies import LateCancellationFee


def build(day: int = 1, hour: int = 8, sqlite: bool = False) -> dict[str, Any]:
    appointments = SqliteAppointmentStore() if sqlite else InMemoryAppointmentStore()
    patients = InMemoryPatientStore()
    notifier = OutboxNotifier()
    bus = EventBus()
    booking = BookingService(
        appointments,
        patients,
        FixedClock(day, hour),
        LateCancellationFee(hours=24, amount=30),
        bus,
    )
    reminders = ReminderService(appointments, patients, notifier)
    reminders.listen(bus)
    return {"booking": booking, "reminders": reminders, "notifier": notifier}


def serve(
    requests: list[dict[str, Any]], day: int = 1, hour: int = 8, sqlite: bool = False
) -> list[dict[str, Any]]:
    """Answer ``requests`` in order (``action``: book, cancel, move, free, remind)."""
    app = build(day, hour, sqlite)
    answers = []
    for request in requests:
        action = request.get("action")
        if action == "remind":
            answers.append(handlers.remind(request, app["reminders"]))
        elif action in ("book", "cancel", "move", "free"):
            answers.append(getattr(handlers, str(action))(request, app["booking"]))
        else:
            answers.append({"status": "error", "reason": f"unknown action {action!r}"})
    return answers
