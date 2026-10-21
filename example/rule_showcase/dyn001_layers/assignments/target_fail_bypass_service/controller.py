"""Controller that reaches through the service into the repository.

It places the order through the service, then reads the stored total straight
from ``service.repository``. That attribute has no static type here, so the
import graph shows no dependency on ``repository``; only the runtime call is
visible. The service is called, so ``require_runtime_calls`` passes and only
``forbid_runtime_calls`` fails.
"""

from __future__ import annotations

from typing import Any


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    service.place(request["id"], request["prices"])
    known = service.repository.get(request["id"])
    return {"status": "ok", "total": known}
