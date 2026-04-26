from enum import Enum
from typing import Annotated

from pythonarchtesting.rules import does_not_have, is_enum


class OrderStatus(Enum):
    __archtest__: Annotated[
        None,
        is_enum(),
        does_not_have("mutate", member_kind="method"),
    ]

    NEW = "new"
    PAID = "paid"
    CANCELLED = "cancelled"
