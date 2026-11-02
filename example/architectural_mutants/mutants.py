"""Catalogue of seeded architectural violations (and equivalent rewrites).

Each mutant changes the correct solution in ``solution/`` by exact text
replacement (``patches``), and where needed by adding (``new_files``),
renaming (``renames``) or removing (``removed_files``) modules, and breaks
exactly one architectural intent of ``reference/``.
``detected_by`` names the markers that state that intent: a mutant counts as
caught only when one of them fails with a violation, not when an unrelated
rule fails or the code merely crashes.

Equivalent variants change the code without changing its architecture; any
failing rule on one of them is a false positive.
"""

from __future__ import annotations

from typing import Any

_PLACE = '    total = service.place(request["id"], request["prices"])\n'
_EMPTY = '        return {"status": "error", "reason": "empty order"}\n'
_APPLY = "        order.apply_total(self._discount.apply(order.total))\n"
_MODELS_IMPORT = "from .models import Order\n"
_TYPING_IMPORT = "from typing import Any\n"

_ONE_FILE = (
    '"""Controller, service and storage in one module."""\n\n'
    "from __future__ import annotations\n\n"
    "from typing import Any\n\n"
    "from .models import Order\n\n\n"
    "def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:\n"
    '    if not request.get("prices"):\n'
    '        return {"status": "error", "reason": "empty order"}\n'
    '    total = service.place(request["id"], request["prices"])\n'
    '    return {"status": "ok", "total": total}\n\n\n'
    "class OrderService:\n"
    "    def __init__(self, repository: Any, discount: Any, bus: Any) -> None:\n"
    "        self._repository = repository\n"
    "        self._discount = discount\n"
    "        self._bus = bus\n\n"
    "    def place(self, order_id: str, prices: list[float]) -> float:\n"
    "        order = Order(order_id)\n"
    "        for price in prices:\n"
    "            order.add(price)\n"
    "        order.apply_total(self._discount.apply(order.total))\n"
    "        order.mark_placed()\n"
    "        self._repository.save(order)\n"
    '        self._bus.publish("order_placed", order.order_id)\n'
    "        return order.total\n\n\n"
    "class OrderRepository:\n"
    "    def __init__(self) -> None:\n"
    "        self._rows: dict[str, Any] = {}\n\n"
    "    def save(self, order: Any) -> None:\n"
    "        self._rows[order.order_id] = order\n\n"
    "    def get(self, order_id: str) -> Any:\n"
    "        return self._rows.get(order_id)\n"
)

_LAYERING = [
    "enforce_layers",
    "forbid_imports",
    "forbid_runtime_calls",
    "require_runtime_calls",
    "enforce_reference_calls",
]
_INJECTION = ["forbid_imports", "forbid_runtime_instantiation"]
_TECHNOLOGY = ["forbid_imports", "forbid_runtime_imports", "forbid_runtime_calls"]

MUTANTS: list[dict[str, Any]] = [
    # O1 layer bypass (intent I1)
    {
        "id": "M01",
        "operator": "O1 layer bypass",
        "description": "controller reads storage through the service's repository",
        "patches": [
            (
                "controller.py",
                _PLACE,
                _PLACE + '    service._repository.get(request["id"])\n',
            )
        ],
        "detected_by": _LAYERING,
    },
    {
        "id": "M02",
        "operator": "O1 layer bypass",
        "description": "controller imports the repository and queries it",
        "patches": [
            (
                "controller.py",
                _TYPING_IMPORT,
                _TYPING_IMPORT + "\nfrom .repository import OrderRepository\n",
            ),
            (
                "controller.py",
                _PLACE,
                _PLACE + '    OrderRepository().get(request["id"])\n',
            ),
        ],
        "detected_by": _LAYERING,
    },
    {
        "id": "M03",
        "operator": "O1 layer bypass",
        "description": "controller reads storage, but only on the empty-order path",
        "patches": [
            (
                "controller.py",
                _EMPTY,
                '        service._repository.get(request.get("id"))\n' + _EMPTY,
            )
        ],
        "detected_by": _LAYERING,
    },
    {
        "id": "M04",
        "operator": "O1 layer bypass",
        "description": "controller computes the total itself and skips the service",
        "patches": [("controller.py", _PLACE, '    total = sum(request["prices"])\n')],
        "detected_by": _LAYERING,
    },
    # O2 broken dependency injection (intent I2)
    {
        "id": "M05",
        "operator": "O2 broken injection",
        "description": "service imports and builds its own repository",
        "patches": [
            (
                "service.py",
                _MODELS_IMPORT,
                _MODELS_IMPORT + "from .repository import OrderRepository\n",
            ),
            (
                "service.py",
                "        self._repository = repository\n",
                "        self._repository = OrderRepository()\n",
            ),
        ],
        "detected_by": _INJECTION,
    },
    {
        "id": "M06",
        "operator": "O2 broken injection",
        "description": "service builds a fresh bus of the injected bus's class",
        "patches": [
            (
                "service.py",
                "        self._bus = bus\n",
                "        self._bus = type(bus)()\n",
            )
        ],
        "detected_by": _INJECTION,
    },
    {
        "id": "M07",
        "operator": "O2 broken injection",
        "description": "place() imports a strategy lazily and replaces the injected one",
        "patches": [
            (
                "service.py",
                "        order = Order(order_id)\n",
                "        from .pricing import PercentDiscount\n\n"
                "        self._discount = PercentDiscount(10)\n"
                "        order = Order(order_id)\n",
            )
        ],
        "detected_by": _INJECTION,
    },
    # O3 foreign write (intent I3)
    {
        "id": "M08",
        "operator": "O3 foreign write",
        "description": "service assigns order.total instead of calling apply_total",
        "patches": [
            (
                "service.py",
                _APPLY,
                "        order.total = self._discount.apply(order.total)\n",
            )
        ],
        "detected_by": ["forbid_foreign_writes"],
    },
    {
        "id": "M09",
        "operator": "O3 foreign write",
        "description": "service sets order.status instead of calling mark_placed",
        "patches": [
            (
                "service.py",
                "        order.mark_placed()\n",
                '        order.status = "placed"\n',
            )
        ],
        "detected_by": ["forbid_foreign_writes"],
    },
    {
        "id": "M10",
        "operator": "O3 foreign write",
        "description": "service fills order.items in place, without an assignment",
        "patches": [
            (
                "service.py",
                "        for price in prices:\n            order.add(price)\n" + _APPLY,
                "        order.items.extend(prices)\n"
                "        order.apply_total(self._discount.apply(sum(prices)))\n",
            )
        ],
        "detected_by": ["forbid_foreign_writes"],
    },
    # O4 forbidden technology (intent I4)
    {
        "id": "M11",
        "operator": "O4 forbidden technology",
        "description": "service imports pickle and serialises the order",
        "patches": [
            ("service.py", _TYPING_IMPORT, "import pickle\n" + _TYPING_IMPORT),
            (
                "service.py",
                "        return order.total\n",
                "        pickle.dumps(order.total)\n        return order.total\n",
            ),
        ],
        "detected_by": _TECHNOLOGY,
    },
    {
        "id": "M12",
        "operator": "O4 forbidden technology",
        "description": "service loads pickle through importlib.import_module",
        "patches": [
            ("service.py", _TYPING_IMPORT, "import importlib\n" + _TYPING_IMPORT),
            (
                "service.py",
                "        return order.total\n",
                '        importlib.import_module("pickle").dumps(order.total)\n'
                "        return order.total\n",
            ),
        ],
        "detected_by": _TECHNOLOGY,
    },
    {
        "id": "M13",
        "operator": "O4 forbidden technology",
        "description": "service opens sqlite3 through __import__",
        "patches": [
            (
                "service.py",
                "        return order.total\n",
                '        __import__("sqlite3").connect(":memory:").close()\n'
                "        return order.total\n",
            )
        ],
        "detected_by": _TECHNOLOGY,
    },
    # O5 skipped collaborator (intents I5 and I1)
    {
        "id": "M14",
        "operator": "O5 skipped collaborator",
        "description": "service hard-codes the discount instead of the strategy",
        "patches": [
            (
                "service.py",
                _APPLY,
                "        order.apply_total(round(order.total * 0.9, 2))\n",
            )
        ],
        "detected_by": ["require_runtime_delegation", "enforce_reference_calls"],
    },
    {
        "id": "M15",
        "operator": "O5 skipped collaborator",
        "description": "service never saves the order",
        "patches": [("service.py", "        self._repository.save(order)\n", "")],
        "detected_by": ["enforce_reference_calls"],
    },
    {
        "id": "M16",
        "operator": "O5 skipped collaborator",
        "description": "service never publishes the event",
        "patches": [
            (
                "service.py",
                '        self._bus.publish("order_placed", order.order_id)\n',
                "",
            )
        ],
        "detected_by": ["enforce_reference_calls"],
    },
    # O6 broken observer (intent I6)
    {
        "id": "M17",
        "operator": "O6 broken pattern",
        "description": "unsubscribe() does nothing",
        "patches": [
            (
                "events.py",
                "        self._listeners.remove(listener)\n",
                "        _ = listener\n",
            )
        ],
        "detected_by": ["enforce_runtime_observer"],
    },
    {
        "id": "M18",
        "operator": "O6 broken pattern",
        "description": "publish() only records the event and notifies nobody",
        "patches": [
            (
                "events.py",
                "        for listener in list(self._listeners):\n"
                "            listener(event, payload)\n",
                "        self.last_event = (event, payload)\n",
            )
        ],
        "detected_by": ["enforce_runtime_observer"],
    },
    # O6 broken singleton (intent I7)
    {
        "id": "M19",
        "operator": "O6 broken pattern",
        "description": "instance() builds a new object on every call",
        "patches": [
            (
                "config.py",
                "        if cls._instance is None:\n"
                "            cls._instance = cls()\n"
                "        return cls._instance\n",
                "        return cls()\n",
            )
        ],
        "detected_by": ["is_runtime_singleton"],
    },
    # O1 layer bypass through a module of the target's own (intent I1): the
    # helper module is new, so ``allow_new_modules`` folds it into the
    # controller, and the call into storage stays a divergence.
    {
        "id": "M20",
        "operator": "O1 layer bypass",
        "description": "controller reads storage through a new helper module",
        "patches": [
            (
                "controller.py",
                _TYPING_IMPORT,
                _TYPING_IMPORT + "\nfrom .lookup import find_order\n",
            ),
            (
                "controller.py",
                _PLACE,
                _PLACE + '    find_order(service._repository, request["id"])\n',
            ),
        ],
        "new_files": {
            "lookup.py": (
                '"""Lookup helpers."""\n\n'
                "from __future__ import annotations\n\n"
                "from typing import Any\n\n\n"
                "def find_order(repository: Any, order_id: str) -> Any:\n"
                "    return repository.get(order_id)\n"
            )
        },
        "detected_by": _LAYERING,
    },
    # O7 dependency cycle (intent I8, `forbid_cycles`): models imports the
    # service, which imports models, and the order calls back into it.
    {
        "id": "M21",
        "operator": "O7 dependency cycle",
        "description": "the order takes its status from a function of the service",
        "patches": [
            (
                "models.py",
                "from __future__ import annotations\n",
                "from __future__ import annotations\n\nfrom . import service\n",
            ),
            (
                "models.py",
                '        self.status = "placed"\n',
                "        self.status = service.placed_status()\n",
            ),
            (
                "service.py",
                "class OrderService:\n",
                "def placed_status() -> str:\n"
                '    return "placed"\n\n\n'
                "class OrderService:\n",
            ),
        ],
        "detected_by": ["forbid_cycles", "enforce_reference_calls"],
    },
    # O8 module interface (intent I9, no marker yet): the service uses a
    # private helper of the models module.
    {
        "id": "M22",
        "operator": "O8 module interface",
        "description": "service calls a private helper of the models module",
        "patches": [
            (
                "models.py",
                "class Order:\n",
                "def _check_price(price: float) -> float:\n"
                "    if price < 0:\n"
                '        raise ValueError("negative price")\n'
                "    return price\n\n\n"
                "class Order:\n",
            ),
            (
                "service.py",
                _MODELS_IMPORT,
                "from .models import Order, _check_price\n",
            ),
            (
                "service.py",
                "            order.add(price)\n",
                "            order.add(_check_price(price))\n",
            ),
        ],
        "detected_by": ["module_interface"],
    },
]

EQUIVALENTS: list[dict[str, Any]] = [
    {
        "id": "E01",
        "operator": "equivalent",
        "description": "controller validates the request differently",
        "patches": [
            (
                "controller.py",
                '    if not request.get("prices"):\n',
                '    if len(request.get("prices") or []) == 0:\n',
            )
        ],
    },
    {
        "id": "E02",
        "operator": "equivalent",
        "description": "service stores the order through a private helper method",
        "patches": [
            (
                "service.py",
                "        self._repository.save(order)\n",
                "        self._store(order)\n",
            ),
            (
                "service.py",
                "        return order.total\n",
                "        return order.total\n\n"
                "    def _store(self, order: Order) -> None:\n"
                "        self._repository.save(order)\n",
            ),
        ],
    },
    {
        "id": "E03",
        "operator": "equivalent",
        "description": "strategy called with a keyword argument",
        "patches": [
            (
                "service.py",
                _APPLY,
                "        order.apply_total(self._discount.apply(total=order.total))\n",
            )
        ],
    },
    {
        "id": "E04",
        "operator": "equivalent",
        "description": "event bus keeps listeners in a dict keyed by id",
        "patches": [
            (
                "events.py",
                "        self._listeners: list[Callable[[str, Any], None]] = []\n",
                "        self._listeners: dict[int, Callable[[str, Any], None]] = {}\n",
            ),
            (
                "events.py",
                "        self._listeners.append(listener)\n",
                "        self._listeners[id(listener)] = listener\n",
            ),
            (
                "events.py",
                "        self._listeners.remove(listener)\n",
                "        self._listeners.pop(id(listener), None)\n",
            ),
            (
                "events.py",
                "        for listener in list(self._listeners):\n",
                "        for listener in list(self._listeners.values()):\n",
            ),
        ],
    },
    {
        "id": "E05",
        "operator": "equivalent",
        "description": "singleton cached in __new__",
        "patches": [
            (
                "config.py",
                "    def __init__(self) -> None:\n",
                "    def __new__(cls) -> AppConfig:\n"
                "        if cls._instance is None:\n"
                "            cls._instance = super().__new__(cls)\n"
                "        return cls._instance\n\n"
                "    def __init__(self) -> None:\n",
            ),
            (
                "config.py",
                "        if cls._instance is None:\n"
                "            cls._instance = cls()\n"
                "        return cls._instance\n",
                "        return cls()\n",
            ),
        ],
    },
    {
        "id": "E06",
        "operator": "equivalent",
        "description": "controller builds its response in a new helper module",
        "patches": [
            (
                "controller.py",
                _TYPING_IMPORT,
                _TYPING_IMPORT + "\nfrom .responses import ok\n",
            ),
            (
                "controller.py",
                '    return {"status": "ok", "total": total}\n',
                "    return ok(total)\n",
            ),
        ],
        "new_files": {
            "responses.py": (
                '"""Response helpers."""\n\n'
                "from __future__ import annotations\n\n"
                "from typing import Any\n\n\n"
                "def ok(total: float) -> dict[str, Any]:\n"
                '    return {"status": "ok", "total": total}\n'
            )
        },
    },
    {
        "id": "E07",
        "operator": "equivalent",
        "description": "repository module renamed to storage",
        "renames": {"repository.py": "storage.py"},
    },
    {
        "id": "E08",
        "operator": "equivalent",
        "description": "controller, service and repository in one module",
        "removed_files": ["controller.py", "service.py", "repository.py"],
        "new_files": {"app.py": _ONE_FILE},
    },
    {
        "id": "E09",
        "operator": "equivalent",
        "description": "service and controller are async",
        "patches": [
            (
                "controller.py",
                "def handle_order(",
                "async def handle_order(",
            ),
            (
                "controller.py",
                _PLACE,
                '    total = await service.place(request["id"], request["prices"])\n',
            ),
            (
                "service.py",
                "    def place(",
                "    async def place(",
            ),
        ],
    },
    {
        "id": "E10",
        "operator": "equivalent",
        "description": "controller function becomes a staticmethod of a class",
        "patches": [
            (
                "controller.py",
                "def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:\n"
                '    if not request.get("prices"):\n'
                + _EMPTY
                + _PLACE
                + '    return {"status": "ok", "total": total}\n',
                "class OrderController:\n"
                "    @staticmethod\n"
                "    def handle_order(\n"
                "        request: dict[str, Any], service: Any\n"
                "    ) -> dict[str, Any]:\n"
                '        if not request.get("prices"):\n'
                '            return {"status": "error", "reason": "empty order"}\n'
                '        total = service.place(request["id"], request["prices"])\n'
                '        return {"status": "ok", "total": total}\n',
            )
        ],
    },
]
