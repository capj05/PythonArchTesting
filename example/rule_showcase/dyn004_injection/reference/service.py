"""Reference service for the DYN004 ``forbid_runtime_instantiation`` showcase.

The service receives its repository from outside (dependency injection), so
a test or another storage can be plugged in. It may call the repository and
create its own domain objects (``models.Order``), but it must never build an
``OrderRepository`` itself — neither in ``__init__`` nor in a method. The
marker sits on ``place``; for a method the instance is built first, with the
rule's ``init``, and that construction is watched too.
"""

from __future__ import annotations

from typing import Annotated, Any

from pythonarchtesting.rules import forbid_runtime_instantiation

from .models import Order


class OrderService:
    def __init__(self, repository: Any) -> None:
        self._repository = repository

    def place(self, order_id: str, prices: list[float]) -> Order:
        __archtest__: Annotated[  # noqa: F842
            None,
            forbid_runtime_instantiation(
                "repository",
                init={"args": [{"$new": "repository.OrderRepository"}]},
                cases=[{"args": ["A1", [10.0, 5.5]]}],
            ),
        ]
        order = Order(order_id, sum(prices))
        self._repository.save(order.order_id, order.total)
        return order
