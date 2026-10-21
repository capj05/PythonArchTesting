"""Reference controller for the DYN001 runtime layering showcase.

The controller receives the service as an argument (dependency injection), so
its parameter carries no type the static import graph could follow: whether
``handle_order`` talks to the service or reaches past it into the repository
only shows when it runs. Two markers state the layering:

- ``require_runtime_calls("service", ...)``: the controller must delegate to
  the service layer;
- ``forbid_runtime_calls("repository", ...)``: it must not call the storage
  layer directly.

The cases only provide arguments that make the code run; what the controller
returns is not checked.
"""

from __future__ import annotations

from typing import Annotated, Any

from pythonarchtesting.rules import forbid_runtime_calls, require_runtime_calls


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    __archtest__: Annotated[  # noqa: F842
        None,
        require_runtime_calls(
            "service",
            cases=[
                {
                    "args": [
                        {"id": "A1", "prices": [10.0, 5.5]},
                        {
                            "$new": "service.OrderService",
                            "args": [{"$new": "repository.OrderRepository"}],
                        },
                    ]
                }
            ],
        ),
        forbid_runtime_calls(
            "repository",
            cases=[
                {
                    "args": [
                        {"id": "A1", "prices": [10.0, 5.5]},
                        {
                            "$new": "service.OrderService",
                            "args": [{"$new": "repository.OrderRepository"}],
                        },
                    ]
                }
            ],
        ),
    ]
    total = service.place(request["id"], request["prices"])
    return {"status": "ok", "total": total}
