"""An appointment store in SQLite: the only module that knows SQL."""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import implements_protocol, implements_runtime_protocol

from ..ports.stores import AppointmentStore

import sqlite3
from typing import Optional

from ..domain.schedule import Appointment, Slot

_SCHEMA = """
CREATE TABLE IF NOT EXISTS appointment (
    id TEXT PRIMARY KEY,
    patient TEXT NOT NULL,
    doctor TEXT NOT NULL,
    day INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    status TEXT NOT NULL,
    fee INTEGER NOT NULL
)
"""


class SqliteAppointmentStore:
    __archtest__: Annotated[
        None,
        implements_protocol(AppointmentStore),
        implements_runtime_protocol(AppointmentStore, cases=[{"args": []}]),
    ]

    """Rows hold the state; the objects handed out are kept so that a change
    made through ``Appointment``'s methods is written back on the next read."""

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.execute(_SCHEMA)
        self._live: dict[str, Appointment] = {}

    def add(self, appointment: Appointment) -> None:
        self._live[appointment.appointment_id] = appointment
        self._write(appointment)

    def get(self, appointment_id: str) -> Optional[Appointment]:
        self._flush()
        if appointment_id in self._live:
            return self._live[appointment_id]
        row = self._db.execute(
            "SELECT id, patient, doctor, day, hour, status, fee "
            "FROM appointment WHERE id = ?",
            (appointment_id,),
        ).fetchone()
        return self._load(row) if row else None

    def holding(self, slot: Slot) -> Optional[Appointment]:
        self._flush()
        row = self._db.execute(
            "SELECT id FROM appointment WHERE doctor = ? AND day = ? AND hour = ? "
            "AND status = 'booked'",
            (slot.doctor, slot.day, slot.hour),
        ).fetchone()
        return self.get(row[0]) if row else None

    def on_day(self, day: int) -> list[Appointment]:
        self._flush()
        rows = self._db.execute(
            "SELECT id FROM appointment WHERE day = ? ORDER BY hour, doctor", (day,)
        ).fetchall()
        return [a for a in (self.get(row[0]) for row in rows) if a is not None]

    def next_id(self) -> str:
        (count,) = self._db.execute("SELECT COUNT(*) FROM appointment").fetchone()
        return f"A{count + 1}"

    def _write(self, appointment: Appointment) -> None:
        slot = appointment.slot
        self._db.execute(
            "INSERT OR REPLACE INTO appointment VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                appointment.appointment_id,
                appointment.patient_id,
                slot.doctor,
                slot.day,
                slot.hour,
                appointment.status,
                appointment.fee,
            ),
        )

    def _flush(self) -> None:
        for appointment in self._live.values():
            self._write(appointment)

    def _load(self, row: tuple) -> Appointment:
        appointment_id, patient, doctor, day, hour, status, fee = row
        appointment = Appointment(appointment_id, patient, Slot(doctor, day, hour))
        if status == "cancelled":
            appointment.cancel(fee)
        elif status == "attended":
            appointment.mark_attended()
        self._live[appointment_id] = appointment
        return appointment
