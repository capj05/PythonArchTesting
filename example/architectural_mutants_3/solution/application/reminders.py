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
        self,
        appointments: AppointmentStore,
        patients: PatientStore,
        notifier: Notifier,
    ) -> None:
        self._appointments = appointments
        self._patients = patients
        self._notifier = notifier

    def listen(self, bus: EventBus) -> None:
        bus.subscribe(AppointmentBooked.name, self.on_booked)
        bus.subscribe(AppointmentMoved.name, self.on_moved)
        bus.subscribe(AppointmentCancelled.name, self.on_cancelled)

    def on_booked(self, event: AppointmentBooked) -> None:
        self._tell(event.patient_id, "Appointment booked", f"See you {event.when}.")

    def on_moved(self, event: AppointmentMoved) -> None:
        self._tell(event.patient_id, "Appointment moved", f"Now {event.when}.")

    def on_cancelled(self, event: AppointmentCancelled) -> None:
        note = f" A fee of {event.fee} applies." if event.fee else ""
        self._tell(event.patient_id, "Appointment cancelled", "Cancelled." + note)

    def run_for(self, day: int) -> int:
        """Remind everyone with an active appointment on ``day``; how many."""
        sent = 0
        for appointment in self._appointments.on_day(day):
            if not appointment.active:
                continue
            slot = appointment.slot
            self._tell(
                appointment.patient_id,
                "Reminder",
                f"Tomorrow at {slot.hour}:00 with {slot.doctor}.",
            )
            sent += 1
        return sent

    def _tell(self, patient_id: str, subject: str, text: str) -> None:
        patient = self._patients.get(patient_id)
        if patient is None:
            return
        self._notifier.send(patient.email, subject, f"{patient.greeting()},\n{text}")
