"""Telling patients about their appointments.

A confirmation goes out when an appointment is booked or moved (the service
listens on the bus), a reminder the day before the visit.
"""

from __future__ import annotations
from ..domain.events import AppointmentBooked, AppointmentCancelled, AppointmentMoved
from ..ports.notifier import Notifier
from ..ports.stores import AppointmentStore, PatientStore
from .bus import EventBus


class ReminderService:

    def __init__(
        self, appointments: AppointmentStore, patients: PatientStore, notifier: Notifier
    ) -> None:
        raise NotImplementedError

    def listen(self, bus: EventBus) -> None:
        raise NotImplementedError

    def on_booked(self, event: AppointmentBooked) -> None:
        raise NotImplementedError

    def on_moved(self, event: AppointmentMoved) -> None:
        raise NotImplementedError

    def on_cancelled(self, event: AppointmentCancelled) -> None:
        raise NotImplementedError

    def run_for(self, day: int) -> int:
        """Remind everyone with an active appointment on ``day``; how many."""
        raise NotImplementedError

    def _tell(self, patient_id: str, subject: str, text: str) -> None:
        raise NotImplementedError
