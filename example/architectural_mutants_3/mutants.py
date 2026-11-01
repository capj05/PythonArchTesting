"""Catalogue of seeded violations of the clinic program (program 3).

The same format as ``../architectural_mutants/mutants.py``: each mutant
changes ``solution/`` by exact text replacement (``patches``), and where
needed by adding (``new_files``), renaming (``renames``) or removing
(``removed_files``) modules, and breaks exactly one architectural intent of
``reference/`` (J1–J11, see the README). ``detected_by`` names the markers
that state that intent. Equivalent variants change the code without changing
its architecture; any failing rule on one of them is a false positive.

Paths are relative to the package and may lie in a subpackage
(``application/booking.py``).
"""

from __future__ import annotations

from typing import Any

_HANDLERS = "api/handlers.py"
_BOOKING = "application/booking.py"
_REMINDERS = "application/reminders.py"
_BOOK_CALL = "        appointment = service.book(patient_id, doctor, day, hour)\n"
_CANCEL_BODY = (
    "        fee = self._policy.fee(appointment, day, hour)\n"
    "        appointment.cancel(fee)\n"
)
_SEND = '        self._notifier.send(patient.email, subject, f"{patient.greeting()},\\n{text}")\n'

# The whole class, removed from the schedule by E03.
_SLOT_CLASS = (
    "class Slot:\n"
    "    def __init__(self, doctor: str, day: int, hour: int) -> None:\n"
    "        _check_hour(hour)\n"
    "        if day < 1:\n"
    '            raise ValueError(f"no day {day}")\n'
    "        self.doctor = doctor\n"
    "        self.day = day\n"
    "        self.hour = hour\n"
    "\n"
    "    def key(self) -> tuple[str, int, int]:\n"
    "        return (self.doctor, self.day, self.hour)\n"
    "\n"
    "    def hours_from(self, day: int, hour: int) -> int:\n"
    "        return (self.day - day) * 24 + (self.hour - hour)\n"
    "\n"
    "    def __eq__(self, other: object) -> bool:\n"
    "        return isinstance(other, Slot) and self.key() == other.key()\n"
    "\n"
    "    def __hash__(self) -> int:\n"
    "        return hash(self.key())\n"
    "\n"
    "    def __repr__(self) -> str:\n"
    '        return f"Slot({self.doctor!r}, day {self.day}, {self.hour}:00)"\n'
    "\n"
    "\n"
)

_API = ["forbid_imports", "forbid_runtime_calls", "enforce_layers"]
_PORTS_ONLY = ["forbid_imports", "enforce_layers", "forbid_runtime_instantiation"]
_PORT = ["implements_protocol", "implements_runtime_protocol"]

MUTANTS: list[dict[str, Any]] = [
    # O1 layer bypass (J3): the handlers talk to the application only.
    {
        "id": "M01",
        "operator": "O1 layer bypass",
        "description": "handler checks the hour with a domain Slot of its own",
        "patches": [
            (
                _HANDLERS,
                "from .serializers import",
                "from ..domain.schedule import Slot\nfrom .serializers import",
            ),
            (
                _HANDLERS,
                _BOOK_CALL,
                "        Slot(doctor, day, hour)\n" + _BOOK_CALL,
            ),
        ],
        "detected_by": ["forbid_imports", "forbid_runtime_calls"],
    },
    {
        "id": "M02",
        "operator": "O1 layer bypass",
        "description": "handler asks the service's store directly (no import)",
        "patches": [
            (
                _HANDLERS,
                _BOOK_CALL,
                _BOOK_CALL + "        service._appointments.on_day(day)\n",
            ),
        ],
        "detected_by": ["forbid_runtime_calls", "enforce_layers"],
    },
    {
        "id": "M03",
        "operator": "O1b bypass through a helper",
        "description": "handler reaches the store through a helper module of the api",
        "new_files": {
            "api/lookup.py": (
                '"""Shortcuts for the handlers."""\n\n'
                "from __future__ import annotations\n\nfrom typing import Any\n\n\n"
                "def appointments_on(service: Any, day: int) -> list[Any]:\n"
                "    return service._appointments.on_day(day)\n"
            )
        },
        "patches": [
            (
                _HANDLERS,
                "from .serializers import",
                "from .lookup import appointments_on\nfrom .serializers import",
            ),
            (
                _HANDLERS,
                _BOOK_CALL,
                _BOOK_CALL + "        appointments_on(service, day)\n",
            ),
        ],
        "detected_by": ["forbid_runtime_calls", "enforce_layers"],
    },
    # O2 broken injection (J6, J8): adapters and policies are injected.
    {
        "id": "M04",
        "operator": "O2 broken injection",
        "description": "the booking service builds its own in-memory store",
        "patches": [
            (
                _BOOKING,
                "from .bus import EventBus\n",
                "from ..adapters.memory_store import InMemoryAppointmentStore\n"
                "from .bus import EventBus\n",
            ),
            (
                _BOOKING,
                "        self._appointments = appointments\n",
                "        self._appointments = InMemoryAppointmentStore()\n",
            ),
        ],
        "detected_by": _PORTS_ONLY,
    },
    {
        "id": "M05",
        "operator": "O2 broken injection",
        "description": "reminders build their own notifier, imported inside the method",
        "patches": [
            (
                _REMINDERS,
                "        sent = 0\n",
                "        from ..adapters.email_notifier import OutboxNotifier\n\n"
                "        self._notifier = OutboxNotifier()\n"
                "        sent = 0\n",
            ),
        ],
        "detected_by": _PORTS_ONLY,
    },
    {
        "id": "M06",
        "operator": "O2 broken injection",
        "description": "cancel applies a fee policy of its own, not the injected one",
        "patches": [
            (
                _BOOKING,
                "from ..domain.patients import Patient\n",
                "from ..domain.patients import Patient\n"
                "from ..domain.policies import LateCancellationFee\n",
            ),
            (
                _BOOKING,
                _CANCEL_BODY,
                "        fee = LateCancellationFee(24, 30).fee(appointment, day, hour)\n"
                "        appointment.cancel(fee)\n",
            ),
        ],
        "detected_by": [
            "forbid_runtime_instantiation",
            "require_runtime_delegation",
        ],
    },
    # O3 foreign write (J11): an appointment changes through its own methods.
    {
        "id": "M07",
        "operator": "O3 foreign write",
        "description": "cancel sets the appointment's status and fee itself",
        "patches": [
            (
                _BOOKING,
                _CANCEL_BODY,
                "        fee = self._policy.fee(appointment, day, hour)\n"
                '        appointment.status = "cancelled"\n'
                "        appointment.fee = fee\n",
            ),
        ],
        "detected_by": ["forbid_foreign_writes"],
    },
    {
        "id": "M08",
        "operator": "O3 foreign write",
        "description": "move replaces the appointment's slot itself",
        "patches": [
            (
                _BOOKING,
                "        appointment.move_to(slot)\n",
                "        appointment.slot = slot\n",
            ),
        ],
        "detected_by": ["forbid_foreign_writes"],
    },
    # O4 forbidden technology (J4): SQL only in the SQLite adapter.
    {
        "id": "M09",
        "operator": "O4 forbidden technology",
        "description": "the booking service logs bookings to SQLite",
        "patches": [
            (
                _BOOKING,
                "from typing import Any, Protocol\n",
                "import sqlite3\nfrom typing import Any, Protocol\n",
            ),
            (
                _BOOKING,
                "        self._appointments.add(appointment)\n",
                "        self._appointments.add(appointment)\n"
                '        sqlite3.connect(":memory:").execute("SELECT 1")\n',
            ),
        ],
        "detected_by": ["forbid_imports", "forbid_runtime_imports"],
    },
    {
        "id": "M10",
        "operator": "O4 forbidden technology",
        "description": "the booking module loads pickle by name when it is imported",
        "patches": [
            (
                _BOOKING,
                "from typing import Any, Protocol\n",
                "import importlib\nfrom typing import Any, Protocol\n",
            ),
            (
                _BOOKING,
                "\n\nclass CancellationPolicy(Protocol):",
                '\n\n_CODEC = importlib.import_module("pick" + "le")\n\n\n'
                "class CancellationPolicy(Protocol):",
            ),
        ],
        "detected_by": ["forbid_runtime_imports"],
    },
    # O5 skipped collaborator (J7): a confirmation goes through the notifier.
    {
        "id": "M11",
        "operator": "O5 skipped collaborator",
        "description": "the booking confirmation is never sent",
        "patches": [
            (
                _REMINDERS,
                '        self._tell(event.patient_id, "Appointment booked", '
                'f"See you {event.when}.")\n',
                "        return None\n",
            ),
        ],
        "detected_by": ["require_runtime_delegation"],
    },
    {
        "id": "M12",
        "operator": "O5 skipped collaborator",
        "description": "reminders write to the outbox list instead of calling send",
        "patches": [
            (
                _REMINDERS,
                _SEND,
                "        outbox = getattr(self._notifier, 'sent', [])\n"
                "        outbox.append((patient.email, subject, text))\n",
            ),
        ],
        "detected_by": ["require_runtime_delegation"],
    },
    # O6 broken pattern (J7): the bus is an observer.
    {
        "id": "M13",
        "operator": "O6 broken pattern",
        "description": "unsubscribing leaves the handler on the bus",
        "patches": [
            (
                "application/bus.py",
                "        self._handlers.get(name, []).remove(handler)\n",
                "        return None\n",
            ),
        ],
        "detected_by": ["enforce_runtime_observer"],
    },
    # O7 dependency cycle (J9) and O10 dependent domain (J1).
    {
        "id": "M14",
        "operator": "O7 dependency cycle",
        "description": "an appointment publishes its own cancellation on a bus",
        "patches": [
            (
                "domain/schedule.py",
                "        self.status = CANCELLED\n",
                "        self.status = CANCELLED\n"
                "        from ..application.bus import EventBus\n\n"
                "        EventBus()\n",
            ),
        ],
        "detected_by": ["forbid_cycles", "forbid_imports", "enforce_layers"],
    },
    {
        "id": "M15",
        "operator": "O10 dependent domain",
        "description": "the cancellation policies read the clock port themselves",
        "patches": [
            (
                "domain/policies.py",
                "from .schedule import Appointment\n",
                "from ..ports.clock import Clock\nfrom .schedule import Appointment\n",
            ),
            (
                "domain/policies.py",
                "class FreeCancellation:\n",
                "class FreeCancellation:\n    clock: Clock | None = None\n\n",
            ),
        ],
        "detected_by": ["forbid_imports", "enforce_layers"],
    },
    # O8 module interface (J10).
    {
        "id": "M16",
        "operator": "O8 module interface",
        "description": "the SQLite store validates hours with the schedule's private helper",
        "patches": [
            (
                "adapters/sqlite_store.py",
                "from ..domain.schedule import Appointment, Slot\n",
                "from ..domain.schedule import Appointment, Slot, _check_hour\n",
            ),
            (
                "adapters/sqlite_store.py",
                "        slot = appointment.slot\n",
                "        slot = appointment.slot\n        _check_hour(slot.hour)\n",
            ),
        ],
        "detected_by": ["module_interface"],
    },
    # O9 broken port (J5).
    {
        "id": "M17",
        "operator": "O9 broken port",
        "description": "the patient store's get is called find",
        "patches": [
            (
                "adapters/memory_store.py",
                "    def get(self, patient_id: str) -> Optional[Patient]:\n",
                "    def find(self, patient_id: str) -> Optional[Patient]:\n",
            ),
        ],
        "detected_by": _PORT,
    },
    {
        "id": "M18",
        "operator": "O9 broken port",
        "description": "the notifier's send requires a priority",
        "patches": [
            (
                "adapters/email_notifier.py",
                "    def send(self, address: str, subject: str, body: str) -> None:\n",
                "    def send(\n        self, address: str, subject: str, body: str, "
                "priority: int\n    ) -> None:\n",
            ),
        ],
        "detected_by": _PORT,
    },
    # Depth: an absolute import through the reference's package name (J2).
    {
        "id": "M19",
        "operator": "O1 layer bypass",
        "description": (
            "the booking module keeps a debug helper that imports the SQLite "
            "adapter through the package name"
        ),
        "patches": [
            (
                _BOOKING,
                "\n\ndef _when(slot: Slot) -> str:",
                "\n\ndef _debug_store() -> Any:\n"
                "    from reference.adapters.sqlite_store import SqliteAppointmentStore\n\n"
                "    return SqliteAppointmentStore\n"
                "\n\ndef _when(slot: Slot) -> str:",
            ),
        ],
        "detected_by": ["forbid_imports", "enforce_layers"],
    },
]

EQUIVALENTS: list[dict[str, Any]] = [
    {
        "id": "E01",
        "operator": "equivalent",
        "description": "the serializers live in the handlers module",
        "removed_files": ["api/serializers.py"],
        "patches": [
            (
                _HANDLERS,
                "from .serializers import RequestError, as_int, error, ok, require\n",
                "\n\nclass RequestError(Exception):\n    pass\n\n\n"
                "def require(request: dict[str, Any], *names: str) -> list[Any]:\n"
                '    missing = [name for name in names if request.get(name) in (None, "")]\n'
                "    if missing:\n"
                "        raise RequestError(f\"missing {', '.join(missing)}\")\n"
                "    return [request[name] for name in names]\n\n\n"
                "def as_int(value: Any, name: str) -> int:\n"
                "    try:\n        return int(value)\n"
                "    except (TypeError, ValueError) as exc:\n"
                '        raise RequestError(f"{name} must be a whole number") from exc\n\n\n'
                "def ok(**fields: Any) -> dict[str, Any]:\n"
                '    return {"status": "ok", **fields}\n\n\n'
                "def error(reason: str) -> dict[str, Any]:\n"
                '    return {"status": "error", "reason": reason}\n',
            ),
        ],
    },
    {
        "id": "E02",
        "operator": "equivalent",
        "description": "the in-memory store module is called in_memory",
        "renames": {"adapters/memory_store.py": "adapters/in_memory.py"},
        "patches": [
            (
                "wiring.py",
                "from .adapters.memory_store import",
                "from .adapters.in_memory import",
            ),
        ],
    },
    {
        "id": "E03",
        "operator": "equivalent",
        "description": "slots get a module of their own, re-exported by the schedule",
        "new_files": {
            "domain/slots.py": (
                '"""A doctor\'s hour on a day."""\n\n'
                "from __future__ import annotations\n\n"
                "WORKING_HOURS = range(8, 16)\n\n\n"
                "class Slot:\n"
                "    def __init__(self, doctor: str, day: int, hour: int) -> None:\n"
                "        if hour not in WORKING_HOURS:\n"
                '            raise ValueError(f"the clinic is closed at {hour}:00")\n'
                "        if day < 1:\n"
                '            raise ValueError(f"no day {day}")\n'
                "        self.doctor = doctor\n        self.day = day\n        self.hour = hour\n\n"
                "    def key(self) -> tuple[str, int, int]:\n"
                "        return (self.doctor, self.day, self.hour)\n\n"
                "    def hours_from(self, day: int, hour: int) -> int:\n"
                "        return (self.day - day) * 24 + (self.hour - hour)\n\n"
                "    def __eq__(self, other: object) -> bool:\n"
                "        return isinstance(other, Slot) and self.key() == other.key()\n\n"
                "    def __hash__(self) -> int:\n        return hash(self.key())\n\n"
                "    def __repr__(self) -> str:\n"
                '        return f"Slot({self.doctor!r}, day {self.day}, {self.hour}:00)"\n'
            )
        },
        "patches": [
            (
                "domain/schedule.py",
                "WORKING_HOURS = range(8, 16)\n",
                "from .slots import WORKING_HOURS, Slot\n\n",
            ),
            ("domain/schedule.py", _SLOT_CLASS, ""),
        ],
    },
    {
        "id": "E04",
        "operator": "equivalent",
        "description": "the bus keeps its handlers as a list of (name, handler) pairs",
        "patches": [
            (
                "application/bus.py",
                "        self._handlers: dict[str, list[Handler]] = {}\n",
                "        self._pairs: list[tuple[str, Handler]] = []\n",
            ),
            (
                "application/bus.py",
                "        self._handlers.setdefault(name, []).append(handler)\n",
                "        self._pairs.append((name, handler))\n",
            ),
            (
                "application/bus.py",
                "        self._handlers.get(name, []).remove(handler)\n",
                "        self._pairs.remove((name, handler))\n",
            ),
            (
                "application/bus.py",
                "        for handler in list(self._handlers.get(event.name, [])):\n",
                "        for handler in [h for n, h in self._pairs if n == event.name]:\n",
            ),
        ],
    },
    {
        "id": "E05",
        "operator": "equivalent",
        "description": "a patient is a dataclass",
        "patches": [
            (
                "domain/patients.py",
                "from __future__ import annotations\n\n\nclass Patient:\n"
                "    def __init__(self, patient_id: str, name: str, email: str) -> None:\n"
                "        if not patient_id:\n",
                "from __future__ import annotations\n\nfrom dataclasses import dataclass\n\n\n"
                "@dataclass\nclass Patient:\n    patient_id: str\n    name: str\n    email: str\n\n"
                "    def __post_init__(self) -> None:\n"
                "        patient_id, email = self.patient_id, self.email\n"
                "        if not patient_id:\n",
            ),
            (
                "domain/patients.py",
                "        self.patient_id = patient_id\n        self.name = name\n"
                "        self.email = email\n",
                "",
            ),
        ],
    },
    {
        "id": "E06",
        "operator": "equivalent",
        "description": "reminders format their text in a private helper method",
        "patches": [
            (
                _REMINDERS,
                "            self._tell(\n"
                "                appointment.patient_id,\n"
                '                "Reminder",\n'
                '                f"Tomorrow at {slot.hour}:00 with {slot.doctor}.",\n'
                "            )\n",
                '            self._tell(appointment.patient_id, "Reminder", '
                "self._reminder(slot))\n",
            ),
            (
                _REMINDERS,
                "    def _tell(self, patient_id: str, subject: str, text: str) -> None:\n",
                "    def _reminder(self, slot: Any) -> str:\n"
                '        return f"Tomorrow at {slot.hour}:00 with {slot.doctor}."\n\n'
                "    def _tell(self, patient_id: str, subject: str, text: str) -> None:\n",
            ),
            (
                _REMINDERS,
                "from __future__ import annotations\n",
                "from __future__ import annotations\n\nfrom typing import Any\n",
            ),
        ],
    },
    {
        "id": "E07",
        "operator": "equivalent",
        "description": "the handlers share one wrapper for errors",
        "patches": [
            (
                _HANDLERS,
                "def cancel(request: dict[str, Any], service: BookingService) -> dict[str, Any]:\n"
                "    try:\n"
                '        (appointment_id,) = require(request, "appointment")\n'
                "        fee = service.cancel(appointment_id)\n"
                "    except (RequestError, BookingError, ValueError) as exc:\n"
                "        return error(str(exc))\n"
                "    return ok(fee=fee)\n",
                "def _guarded(action: Any) -> dict[str, Any]:\n"
                "    try:\n        return action()\n"
                "    except (RequestError, BookingError, ValueError) as exc:\n"
                "        return error(str(exc))\n\n\n"
                "def cancel(request: dict[str, Any], service: BookingService) -> dict[str, Any]:\n"
                "    def run() -> dict[str, Any]:\n"
                '        (appointment_id,) = require(request, "appointment")\n'
                "        return ok(fee=service.cancel(appointment_id))\n\n"
                "    return _guarded(run)\n",
            ),
        ],
    },
    {
        "id": "E08",
        "operator": "equivalent",
        "description": "the adapters inherit from the ports they implement",
        "patches": [
            (
                "adapters/memory_store.py",
                "from ..domain.schedule import Appointment, Slot\n",
                "from ..domain.schedule import Appointment, Slot\n"
                "from ..ports.stores import AppointmentStore, PatientStore\n",
            ),
            (
                "adapters/memory_store.py",
                "class InMemoryAppointmentStore:\n",
                "class InMemoryAppointmentStore(AppointmentStore):\n",
            ),
            (
                "adapters/memory_store.py",
                "class InMemoryPatientStore:\n",
                "class InMemoryPatientStore(PatientStore):\n",
            ),
            (
                "adapters/email_notifier.py",
                "from __future__ import annotations\n",
                "from __future__ import annotations\n\nfrom ..ports.notifier import Notifier\n",
            ),
            (
                "adapters/email_notifier.py",
                "class OutboxNotifier:\n",
                "class OutboxNotifier(Notifier):\n",
            ),
        ],
    },
]
