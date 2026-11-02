"""Slots and appointments.

An appointment changes state only through its own methods; other modules use
this module through ``Slot``, ``Appointment``, ``free_slots`` and
``WORKING_HOURS``.
"""

from __future__ import annotations

WORKING_HOURS = range(8, 16)
BOOKED = "booked"
CANCELLED = "cancelled"
ATTENDED = "attended"


class Slot:
    def __init__(self, doctor: str, day: int, hour: int) -> None:
        _check_hour(hour)
        if day < 1:
            raise ValueError(f"no day {day}")
        self.doctor = doctor
        self.day = day
        self.hour = hour

    def key(self) -> tuple[str, int, int]:
        return (self.doctor, self.day, self.hour)

    def hours_from(self, day: int, hour: int) -> int:
        return (self.day - day) * 24 + (self.hour - hour)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Slot) and self.key() == other.key()

    def __hash__(self) -> int:
        return hash(self.key())

    def __repr__(self) -> str:
        return f"Slot({self.doctor!r}, day {self.day}, {self.hour}:00)"


class Appointment:
    def __init__(self, appointment_id: str, patient_id: str, slot: Slot) -> None:
        self.appointment_id = appointment_id
        self.patient_id = patient_id
        self.slot = slot
        self.status = BOOKED
        self.fee = 0
        self.history: list[Slot] = []

    @property
    def active(self) -> bool:
        return self.status == BOOKED

    def cancel(self, fee: int) -> None:
        if not self.active:
            raise ValueError(f"{self.appointment_id} is {self.status}")
        self.status = CANCELLED
        self.fee = fee

    def move_to(self, slot: Slot) -> None:
        if not self.active:
            raise ValueError(f"{self.appointment_id} is {self.status}")
        self.history.append(self.slot)
        self.slot = slot

    def mark_attended(self) -> None:
        if not self.active:
            raise ValueError(f"{self.appointment_id} is {self.status}")
        self.status = ATTENDED


def free_slots(doctor: str, day: int, taken: set[Slot]) -> list[Slot]:
    """The slots of ``doctor`` on ``day`` that nobody holds, in time order."""
    return [
        slot
        for slot in (Slot(doctor, day, hour) for hour in WORKING_HOURS)
        if slot not in taken
    ]


def _check_hour(hour: int) -> None:
    if hour not in WORKING_HOURS:
        raise ValueError(f"the clinic is closed at {hour}:00")
