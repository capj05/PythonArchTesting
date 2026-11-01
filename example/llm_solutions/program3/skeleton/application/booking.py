"""Booking, cancelling and moving appointments."""

from __future__ import annotations
from typing import Any, Protocol
from ..domain.events import AppointmentBooked, AppointmentCancelled, AppointmentMoved
from ..domain.patients import Patient
from ..domain.schedule import Appointment, Slot, free_slots
from ..ports.clock import Clock
from ..ports.stores import AppointmentStore, PatientStore
from .bus import EventBus


class CancellationPolicy(Protocol):

    def fee(self, appointment: Appointment, day: int, hour: int) -> int: ...


class BookingError(Exception):
    pass


class BookingService:

    def __init__(
        self,
        appointments: AppointmentStore,
        patients: PatientStore,
        clock: Clock,
        policy: CancellationPolicy,
        bus: EventBus,
    ) -> None:
        raise NotImplementedError

    def register(self, patient_id: str, name: str, email: str) -> Patient:
        raise NotImplementedError

    def book(self, patient_id: str, doctor: str, day: int, hour: int) -> Appointment:
        raise NotImplementedError

    def cancel(self, appointment_id: str) -> int:
        raise NotImplementedError

    def move(self, appointment_id: str, day: int, hour: int) -> Appointment:
        raise NotImplementedError

    def free(self, doctor: str, day: int) -> list[Slot]:
        raise NotImplementedError

    def _existing(self, appointment_id: str) -> Appointment:
        raise NotImplementedError

    def _open_slot(self, doctor: str, day: int, hour: int) -> Slot:
        raise NotImplementedError


def _when(slot: Slot) -> str:
    raise NotImplementedError


def summary(appointment: Appointment) -> dict[str, Any]:
    raise NotImplementedError
