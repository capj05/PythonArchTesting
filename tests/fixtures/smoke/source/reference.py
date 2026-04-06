from typing import Annotated

from src.rules import required_entity_signature


def add_numbers(a: int, b: int) -> int:
    __archtest__: Annotated[  # noqa: F842
        None,
        required_entity_signature(mode="exact"),
    ]
    return a + b


def filter_even(values: list[int]) -> list[int]:
    return [value for value in values if value % 2 == 0]
