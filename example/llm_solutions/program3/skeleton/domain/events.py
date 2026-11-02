"""What happened to an appointment, for whoever listens."""

from __future__ import annotations


class AppointmentEvent:
    name = "appointment"

    def __init__(self, appointment_id: str, patient_id: str) -> None:
        raise NotImplementedError


class AppointmentBooked(AppointmentEvent):
    name = "booked"

    def __init__(self, appointment_id: str, patient_id: str, when: str) -> None:
        raise NotImplementedError


class AppointmentCancelled(AppointmentEvent):
    name = "cancelled"

    def __init__(self, appointment_id: str, patient_id: str, fee: int) -> None:
        raise NotImplementedError


class AppointmentMoved(AppointmentEvent):
    name = "moved"

    def __init__(self, appointment_id: str, patient_id: str, when: str) -> None:
        raise NotImplementedError
