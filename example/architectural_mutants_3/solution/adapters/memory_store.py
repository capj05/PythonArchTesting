"""Stores that keep everything in memory."""

from __future__ import annotations

from typing import Optional

from ..domain.patients import Patient
from ..domain.schedule import Appointment, Slot


class InMemoryAppointmentStore:
    def __init__(self, appointments: Optional[list[Appointment]] = None) -> None:
        self._items = {a.appointment_id: a for a in appointments or []}
        self._counter = len(self._items)

    def add(self, appointment: Appointment) -> None:
        self._items[appointment.appointment_id] = appointment

    def get(self, appointment_id: str) -> Optional[Appointment]:
        return self._items.get(appointment_id)

    def holding(self, slot: Slot) -> Optional[Appointment]:
        for appointment in self._items.values():
            if appointment.slot == slot and appointment.active:
                return appointment
        return None

    def on_day(self, day: int) -> list[Appointment]:
        found = [a for a in self._items.values() if a.slot.day == day]
        return sorted(found, key=lambda a: (a.slot.hour, a.slot.doctor))

    def next_id(self) -> str:
        self._counter += 1
        return f"A{self._counter}"


class InMemoryPatientStore:
    def __init__(self, patients: Optional[list[Patient]] = None) -> None:
        self._items = {p.patient_id: p for p in patients or []}

    def add(self, patient: Patient) -> None:
        self._items[patient.patient_id] = patient

    def get(self, patient_id: str) -> Optional[Patient]:
        return self._items.get(patient_id)
