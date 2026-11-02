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
        raise NotImplementedError

    def key(self) -> tuple[str, int, int]:
        raise NotImplementedError

    def hours_from(self, day: int, hour: int) -> int:
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        raise NotImplementedError

    def __hash__(self) -> int:
        raise NotImplementedError

    def __repr__(self) -> str:
        raise NotImplementedError


class Appointment:

    def __init__(self, appointment_id: str, patient_id: str, slot: Slot) -> None:
        raise NotImplementedError

    @property
    def active(self) -> bool:
        raise NotImplementedError

    def cancel(self, fee: int) -> None:
        raise NotImplementedError

    def move_to(self, slot: Slot) -> None:
        raise NotImplementedError

    def mark_attended(self) -> None:
        raise NotImplementedError


def free_slots(doctor: str, day: int, taken: set[Slot]) -> list[Slot]:
    """The slots of ``doctor`` on ``day`` that nobody holds, in time order."""
    raise NotImplementedError


def _check_hour(hour: int) -> None:
    raise NotImplementedError
