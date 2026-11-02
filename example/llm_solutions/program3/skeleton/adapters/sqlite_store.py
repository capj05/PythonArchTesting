"""An appointment store in SQLite: the only module that knows SQL."""

from __future__ import annotations
import sqlite3
from typing import Optional
from ..domain.schedule import Appointment, Slot

_SCHEMA = "\nCREATE TABLE IF NOT EXISTS appointment (\n    id TEXT PRIMARY KEY,\n    patient TEXT NOT NULL,\n    doctor TEXT NOT NULL,\n    day INTEGER NOT NULL,\n    hour INTEGER NOT NULL,\n    status TEXT NOT NULL,\n    fee INTEGER NOT NULL\n)\n"


class SqliteAppointmentStore:
    """Rows hold the state; the objects handed out are kept so that a change
    made through ``Appointment``'s methods is written back on the next read."""

    def __init__(self, path: str = ":memory:") -> None:
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

    def _write(self, appointment: Appointment) -> None:
        raise NotImplementedError

    def _flush(self) -> None:
        raise NotImplementedError

    def _load(self, row: tuple) -> Appointment:
        raise NotImplementedError
