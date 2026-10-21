"""Controller that re-reads the stored total from the repository itself."""

from __future__ import annotations

from typing import Any


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    service.place(request["id"], request["prices"])
    total = service.repository.get(request["id"])
    return {"status": "ok", "total": total}
