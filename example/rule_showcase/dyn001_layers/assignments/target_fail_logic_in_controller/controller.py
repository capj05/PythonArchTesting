"""Controller that does the service's work itself.

It computes the total in place and never calls the service, so the service
layer is skipped: ``require_runtime_calls`` fails.
"""

from __future__ import annotations

from typing import Any


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    _ = service
    total = sum(request["prices"])
    return {"status": "ok", "total": total}
