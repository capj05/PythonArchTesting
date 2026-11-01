"""Where appointments and patients are kept."""

from __future__ import annotations
from typing import Optional, Protocol
from ..domain.patients import Patient
from ..domain.schedule import Appointment, Slot


class AppointmentStore(Protocol):

    def add(self, appointment: Appointment) -> None: ...

    def get(self, appointment_id: str) -> Optional[Appointment]: ...

    def holding(self, slot: Slot) -> Optional[Appointment]: ...

    def on_day(self, day: int) -> list[Appointment]: ...

    def next_id(self) -> str: ...


class PatientStore(Protocol):

    def add(self, patient: Patient) -> None: ...

    def get(self, patient_id: str) -> Optional[Patient]: ...
