"""Reference controller for the DYN001 ``enforce_reference_calls`` showcase.

One marker on the entry point describes the whole layered design: the
reference is run with the case, every call between two of its modules is
recorded (controller -> service, service -> repository, service -> notifier),
and a target may only make those module-to-module calls. With
``require_all=True`` it must make all of them, too.

The case wires the layers with ``$new`` from the target's own classes. Only
the calls are compared; the totals the code computes are not.
"""

from __future__ import annotations

from typing import Annotated, Any

from pythonarchtesting.rules import enforce_reference_calls


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    __archtest__: Annotated[  # noqa: F842
        None,
        enforce_reference_calls(
            require_all=True,
            cases=[
                {
                    "args": [
                        {"id": "A1", "prices": [10.0, 5.5]},
                        {
                            "$new": "service.OrderService",
                            "args": [
                                {"$new": "repository.OrderRepository"},
                                {"$new": "notifier.Notifier"},
                            ],
                        },
                    ]
                }
            ],
        ),
    ]
    total = service.place(request["id"], request["prices"])
    return {"status": "ok", "total": total}
