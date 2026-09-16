"""linear_pipeline omits the 'cleaned' stage marker -- enforce_flow should fail."""

from typing import Annotated

from pythonarchtesting.rules import flow


def linear_pipeline() -> str:
    payload = "data"
    __archtest__: Annotated[None, flow("acquired", variable="payload")]
    payload = payload.strip()
    # 'cleaned' stage marker removed -- enforce_flow should fail
    payload = f"{payload}-id"
    __archtest__: Annotated[None, flow("saved", variable="payload")]  # noqa: F811
    return payload


def branched_pipeline(condition: bool) -> int:
    counter = 0
    __archtest__: Annotated[None, flow("start", variable="counter")]
    if condition:
        counter = counter + 1
        __archtest__: Annotated[None, flow("branch_a", variable="counter")]  # noqa: F811
    else:
        counter = counter - 1
        __archtest__: Annotated[None, flow("branch_b", variable="counter")]  # noqa: F811
    counter = counter * 2
    __archtest__: Annotated[None, flow("end", variable="counter")]  # noqa: F811
    return counter
