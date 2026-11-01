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
        self._appointments = appointments
        self._patients = patients
        self._clock = clock
        self._policy = policy
        self._bus = bus

    def register(self, patient_id: str, name: str, email: str) -> Patient:
        known = self._patients.get(patient_id)
        if known is not None:
            return known
        patient = Patient(patient_id, name, email)
        self._patients.add(patient)
        return patient

    def book(self, patient_id: str, doctor: str, day: int, hour: int) -> Appointment:
        if self._patients.get(patient_id) is None:
            raise BookingError(f"unknown patient {patient_id}")
        slot = self._open_slot(doctor, day, hour)
        appointment = Appointment(self._appointments.next_id(), patient_id, slot)
        self._appointments.add(appointment)
        self._bus.publish(
            AppointmentBooked(appointment.appointment_id, patient_id, _when(slot))
        )
        return appointment

    def cancel(self, appointment_id: str) -> int:
        appointment = self._existing(appointment_id)
        day, hour = self._clock.now()
        fee = self._policy.fee(appointment, day, hour)
        appointment.cancel(fee)
        self._bus.publish(
            AppointmentCancelled(appointment_id, appointment.patient_id, fee)
        )
        return fee

    def move(self, appointment_id: str, day: int, hour: int) -> Appointment:
        appointment = self._existing(appointment_id)
        slot = self._open_slot(appointment.slot.doctor, day, hour)
        appointment.move_to(slot)
        self._bus.publish(
            AppointmentMoved(appointment_id, appointment.patient_id, _when(slot))
        )
        return appointment

    def free(self, doctor: str, day: int) -> list[Slot]:
        taken = {a.slot for a in self._appointments.on_day(day) if a.active}
        return free_slots(doctor, day, taken)

    def _existing(self, appointment_id: str) -> Appointment:
        appointment = self._appointments.get(appointment_id)
        if appointment is None:
            raise BookingError(f"no appointment {appointment_id}")
        return appointment

    def _open_slot(self, doctor: str, day: int, hour: int) -> Slot:
        try:
            slot = Slot(doctor, day, hour)
        except ValueError as exc:
            raise BookingError(str(exc)) from exc
        today, now = self._clock.now()
        if slot.hours_from(today, now) <= 0:
            raise BookingError(f"{slot} is in the past")
        holder = self._appointments.holding(slot)
        if holder is not None and holder.active:
            raise BookingError(f"{slot} is taken")
        return slot


def _when(slot: Slot) -> str:
    return f"day {slot.day} at {slot.hour}:00 with {slot.doctor}"


def summary(appointment: Appointment) -> dict[str, Any]:
    return {
        "id": appointment.appointment_id,
        "patient": appointment.patient_id,
        "doctor": appointment.slot.doctor,
        "day": appointment.slot.day,
        "hour": appointment.slot.hour,
        "status": appointment.status,
        "fee": appointment.fee,
    }
