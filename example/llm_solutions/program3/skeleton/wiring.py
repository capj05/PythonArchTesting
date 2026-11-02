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
    raise NotImplementedError


def serve(
    requests: list[dict[str, Any]], day: int = 1, hour: int = 8, sqlite: bool = False
) -> list[dict[str, Any]]:
    """Answer ``requests`` in order (``action``: book, cancel, move, free, remind)."""
    raise NotImplementedError
