"""Stores that keep everything in memory."""

from __future__ import annotations
from typing import Optional
from ..domain.patients import Patient
from ..domain.schedule import Appointment, Slot


class InMemoryAppointmentStore:

    def __init__(self, appointments: Optional[list[Appointment]] = None) -> None:
        raise NotImplementedError

    def add(self, appointment: Appointment) -> None:
        raise NotImplementedError

    def get(self, appointment_id: str) -> Optional[Appointment]:
        raise NotImplementedError

    def holding(self, slot: Slot) -> Optional[Appointment]:
        raise NotImplementedError

    def on_day(self, day: int) -> list[Appointment]:
        raise NotImplementedError

    def next_id(self) -> str:
        raise NotImplementedError


class InMemoryPatientStore:

    def __init__(self, patients: Optional[list[Patient]] = None) -> None:
        raise NotImplementedError

    def add(self, patient: Patient) -> None:
        raise NotImplementedError

    def get(self, patient_id: str) -> Optional[Patient]:
        raise NotImplementedError
