from typing import Annotated

from pythonarchtesting.rules import (
    does_not_have,
    required_attribute,
    required_constructor,
)


class Money:
    __archtest__: Annotated[
        None,
        required_constructor(signature_mode="any"),
        required_attribute("amount", storage="instance"),
        required_attribute("currency", storage="instance"),
        does_not_have("set_amount", member_kind="method"),
        does_not_have("update_currency", member_kind="method"),
    ]

    def __init__(self, amount: int, currency: str) -> None:
        self.amount = amount
        self.currency = currency
