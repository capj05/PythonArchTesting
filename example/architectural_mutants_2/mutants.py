"""Catalogue of seeded violations of the ports-and-adapters program.

The same format as ``../architectural_mutants/mutants.py``: each mutant
changes ``solution/`` by exact text replacement (``patches``), and where
needed by adding (``new_files``), renaming (``renames``) or removing
(``removed_files``) modules, and breaks exactly one architectural intent of
``reference/``. ``detected_by`` names the markers that state that intent.
Equivalent variants change the code without changing its architecture; any
failing rule on one of them is a false positive.
"""

from __future__ import annotations

from typing import Any

_LEND = '    due = service.lend(request["book"], request["member"])\n'
_GIVE_BACK = '    returned = service.give_back(request["book"])\n'
_EARLY = (
    '        return {"status": "error", "reason": "book and member are required"}\n'
)
_TYPING_IMPORT = "from typing import Any\n"
_APP_IMPORTS = "from .ports import Clock, LoanStore, Notifier\n"
_SEND = '        self._notifier.send(member, f"{book_id} is due on day {loan.due}")\n'

_DRIVING = [
    "enforce_layers",
    "forbid_imports",
    "forbid_runtime_calls",
    "require_runtime_calls",
    "enforce_reference_calls",
]
_PORTS_ONLY = ["enforce_layers", "forbid_imports", "forbid_runtime_instantiation"]
_PORT_CONTRACT = ["implements_protocol", "implements_runtime_protocol"]

_ADAPTERS = '''"""Driven adapters: the loan store, a fixed clock and the notifier."""

from __future__ import annotations

from .domain import Loan


class InMemoryLoanStore:
    def __init__(self, loans: list[Loan] | None = None) -> None:
        self._loans = {loan.book_id: loan for loan in loans or []}

    def add(self, loan: Loan) -> None:
        self._loans[loan.book_id] = loan

    def find(self, book_id: str) -> Loan | None:
        return self._loans.get(book_id)


class FixedClock:
    def __init__(self, day: int) -> None:
        self._day = day

    def today(self) -> int:
        return self._day


class OutboxNotifier:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, member: str, text: str) -> None:
        self.sent.append((member, text))
'''

MUTANTS: list[dict[str, Any]] = [
    # O1 driving adapter bypasses the application (intent H4)
    {
        "id": "M01",
        "operator": "O1 layer bypass",
        "description": "handler reads the store through the service's attribute",
        "patches": [
            ("api.py", _LEND, _LEND + '    service._store.find(request["book"])\n')
        ],
        "detected_by": _DRIVING,
    },
    {
        "id": "M02",
        "operator": "O1 layer bypass",
        "description": "handler imports the store adapter and queries a new one",
        "patches": [
            (
                "api.py",
                _TYPING_IMPORT,
                _TYPING_IMPORT + "\nfrom .adapters_memory import InMemoryLoanStore\n",
            ),
            (
                "api.py",
                _GIVE_BACK,
                '    InMemoryLoanStore().find(request["book"])\n' + _GIVE_BACK,
            ),
        ],
        "detected_by": _DRIVING,
    },
    {
        "id": "M03",
        "operator": "O1 layer bypass",
        "description": "handler reads the store through a new helper module",
        "patches": [
            (
                "api.py",
                _TYPING_IMPORT,
                _TYPING_IMPORT + "\nfrom .lookup import find_loan\n",
            ),
            (
                "api.py",
                _LEND,
                _LEND + '    find_loan(service._store, request["book"])\n',
            ),
        ],
        "new_files": {
            "lookup.py": (
                '"""Lookup helpers."""\n\n'
                "from __future__ import annotations\n\n"
                "from typing import Any\n\n\n"
                "def find_loan(store: Any, book_id: str) -> Any:\n"
                "    return store.find(book_id)\n"
            )
        },
        "detected_by": _DRIVING,
    },
    {
        "id": "M04",
        "operator": "O1 layer bypass",
        "description": "handler builds a loan itself on the early-exit path",
        "patches": [
            (
                "api.py",
                _TYPING_IMPORT,
                _TYPING_IMPORT + "\nfrom .domain import Loan\n",
            ),
            (
                "api.py",
                _EARLY,
                '        Loan(str(request.get("book")), "", 0).close()\n' + _EARLY,
            ),
        ],
        "detected_by": _DRIVING,
    },
    # O2 the application depends on adapters (intent H2)
    {
        "id": "M05",
        "operator": "O2 broken injection",
        "description": "service imports the notifier adapter and builds its own",
        "patches": [
            (
                "application.py",
                _APP_IMPORTS,
                "from .adapters_notify import OutboxNotifier\n" + _APP_IMPORTS,
            ),
            (
                "application.py",
                "        self._notifier = notifier\n",
                "        self._notifier = OutboxNotifier()\n",
            ),
        ],
        "detected_by": _PORTS_ONLY,
    },
    {
        "id": "M06",
        "operator": "O2 broken injection",
        "description": "lend() imports a clock lazily and replaces the injected one",
        "patches": [
            (
                "application.py",
                "        current = self._store.find(book_id)\n",
                "        from .adapters_memory import FixedClock\n\n"
                "        self._clock = FixedClock(self._clock.today())\n"
                "        current = self._store.find(book_id)\n",
            )
        ],
        "detected_by": _PORTS_ONLY,
    },
    {
        "id": "M07",
        "operator": "O2 broken injection",
        "description": "service builds a fresh store of the injected store's class",
        "patches": [
            (
                "application.py",
                "        self._store = store\n",
                "        self._store = type(store)()\n",
            )
        ],
        "detected_by": _PORTS_ONLY,
    },
    # O3 foreign write (intent H5)
    {
        "id": "M08",
        "operator": "O3 foreign write",
        "description": "give_back() sets loan.returned instead of calling close()",
        "patches": [
            (
                "application.py",
                "        loan.close()\n",
                "        loan.returned = True\n",
            )
        ],
        "detected_by": ["forbid_foreign_writes"],
    },
    # O5 skipped collaborator (intent H6)
    {
        "id": "M09",
        "operator": "O5 skipped collaborator",
        "description": "lend() never notifies the member",
        "patches": [("application.py", _SEND, "")],
        "detected_by": ["require_runtime_delegation", "enforce_reference_calls"],
    },
    # O9 an adapter no longer satisfies its port (intent H3)
    {
        "id": "M10",
        "operator": "O9 broken port",
        "description": "the notifier's send() is renamed to notify()",
        "patches": [
            (
                "adapters_notify.py",
                "    def send(self, member: str, text: str) -> None:\n",
                "    def notify(self, member: str, text: str) -> None:\n",
            ),
            ("application.py", "self._notifier.send(", "self._notifier.notify("),
        ],
        "detected_by": _PORT_CONTRACT,
    },
    {
        "id": "M11",
        "operator": "O9 broken port",
        "description": "the store's find() requires a second argument",
        "patches": [
            (
                "adapters_memory.py",
                "    def find(self, book_id: str) -> Loan | None:\n",
                "    def find(self, book_id: str, member: str) -> Loan | None:\n",
            ),
            (
                "application.py",
                "        current = self._store.find(book_id)\n",
                '        current = self._store.find(book_id, "")\n',
            ),
            (
                "application.py",
                "        loan = self._store.find(book_id)\n",
                '        loan = self._store.find(book_id, "")\n',
            ),
        ],
        "detected_by": _PORT_CONTRACT,
    },
    # O10 the domain depends on the outside (intent H1)
    {
        "id": "M12",
        "operator": "O10 dependent domain",
        "description": "close() tells the member through the notifier adapter",
        "patches": [
            (
                "domain.py",
                "        self.returned = True\n",
                "        from .adapters_notify import OutboxNotifier\n\n"
                "        self.returned = True\n"
                '        OutboxNotifier().send(self.member, f"{self.book_id} returned")\n',
            )
        ],
        "detected_by": ["enforce_layers", "forbid_imports", "enforce_reference_calls"],
    },
    # O7 dependency cycle (intent H8)
    {
        "id": "M13",
        "operator": "O7 dependency cycle",
        "description": "the loan takes its closed state from a function of the service",
        # The import sits inside close(): at module level it would fail with
        # an ImportError whenever the domain is imported first.
        "patches": [
            (
                "domain.py",
                "        self.returned = True\n",
                "        from . import application\n\n"
                "        self.returned = application.closed_state()\n",
            ),
            (
                "application.py",
                "class LendingService:\n",
                "def closed_state() -> bool:\n    return True\n\n\nclass LendingService:\n",
            ),
        ],
        "detected_by": ["forbid_cycles", "forbid_imports", "enforce_reference_calls"],
    },
]

EQUIVALENTS: list[dict[str, Any]] = [
    {
        "id": "E01",
        "operator": "equivalent",
        "description": "handler validates the request differently",
        "patches": [
            (
                "api.py",
                '    if not request.get("book") or not request.get("member"):\n',
                '    if not all(request.get(key) for key in ("book", "member")):\n',
            )
        ],
    },
    {
        "id": "E02",
        "operator": "equivalent",
        "description": "store adapter module renamed to storage",
        "renames": {"adapters_memory.py": "storage.py"},
        "patches": [
            (
                "wiring.py",
                "from .adapters_memory import",
                "from .storage import",
            )
        ],
    },
    {
        "id": "E03",
        "operator": "equivalent",
        "description": "both driven adapters in one module",
        "removed_files": ["adapters_memory.py", "adapters_notify.py"],
        "new_files": {"adapters.py": _ADAPTERS},
        "patches": [
            (
                "wiring.py",
                "from .adapters_memory import FixedClock, InMemoryLoanStore\n"
                "from .adapters_notify import OutboxNotifier\n",
                "from .adapters import FixedClock, InMemoryLoanStore, OutboxNotifier\n",
            )
        ],
    },
    {
        "id": "E04",
        "operator": "equivalent",
        "description": "handler builds its response in a new helper module",
        "patches": [
            (
                "api.py",
                _TYPING_IMPORT,
                _TYPING_IMPORT + "\nfrom .responses import ok\n",
            ),
            (
                "api.py",
                '    return {"status": "ok", "due": due}\n',
                "    return ok(due)\n",
            ),
        ],
        "new_files": {
            "responses.py": (
                '"""Response helpers."""\n\n'
                "from __future__ import annotations\n\n"
                "from typing import Any\n\n\n"
                "def ok(due: int) -> dict[str, Any]:\n"
                '    return {"status": "ok", "due": due}\n'
            )
        },
    },
    {
        "id": "E05",
        "operator": "equivalent",
        "description": "service notifies through a private helper method",
        "patches": [
            (
                "application.py",
                _SEND,
                '        self._notify(member, f"{book_id} is due on day {loan.due}")\n',
            ),
            (
                "application.py",
                "        loan.close()\n        return True\n",
                "        loan.close()\n        return True\n\n"
                "    def _notify(self, member: str, text: str) -> None:\n"
                "        self._notifier.send(member, text)\n",
            ),
        ],
    },
    {
        "id": "E06",
        "operator": "equivalent",
        "description": "the loan is a dataclass",
        "patches": [
            (
                "domain.py",
                "from __future__ import annotations\n",
                "from __future__ import annotations\n\nfrom dataclasses import dataclass\n",
            ),
            (
                "domain.py",
                "class Loan:\n"
                "    def __init__(self, book_id: str, member: str, due: int) -> None:\n"
                "        self.book_id = book_id\n"
                "        self.member = member\n"
                "        self.due = due\n"
                "        self.returned = False\n",
                "@dataclass\n"
                "class Loan:\n"
                "    book_id: str\n"
                "    member: str\n"
                "    due: int\n"
                "    returned: bool = False\n",
            ),
        ],
    },
]
