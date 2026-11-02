"""What happened to an appointment, for whoever listens."""

from __future__ import annotations


class AppointmentEvent:
    name = "appointment"

    def __init__(self, appointment_id: str, patient_id: str) -> None:
        self.appointment_id = appointment_id
        self.patient_id = patient_id


class AppointmentBooked(AppointmentEvent):
    name = "booked"

    def __init__(self, appointment_id: str, patient_id: str, when: str) -> None:
        super().__init__(appointment_id, patient_id)
        self.when = when


class AppointmentCancelled(AppointmentEvent):
    name = "cancelled"

    def __init__(self, appointment_id: str, patient_id: str, fee: int) -> None:
        super().__init__(appointment_id, patient_id)
        self.fee = fee


class AppointmentMoved(AppointmentEvent):
    name = "moved"

    def __init__(self, appointment_id: str, patient_id: str, when: str) -> None:
        super().__init__(appointment_id, patient_id)
        self.when = when
