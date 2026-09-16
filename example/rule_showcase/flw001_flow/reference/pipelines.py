"""Reference pipelines exercising `flow` and `enforce_flow` markers."""

from typing import Annotated

from pythonarchtesting.rules import enforce_flow, flow


def linear_pipeline() -> str:
    """Three stages, must occur in order: acquired -> cleaned -> saved.

    All ``flow`` markers track the **same** variable ``payload``;
    ``enforce_flow`` is matched only when every stage's tracked variable
    is identical (otherwise the compiler emits ``ambiguous_variable``).
    """
    payload = "data"
    __archtest__: Annotated[None, flow("acquired", variable="payload")]
    payload = payload.strip()
    __archtest__: Annotated[None, flow("cleaned", variable="payload")]  # noqa: F811
    payload = f"{payload}-id"
    __archtest__: Annotated[None, flow("saved", variable="payload")]  # noqa: F811
    __archtest__: Annotated[  # noqa: F811
        None, enforce_flow(["acquired", "cleaned", "saved"])
    ]
    return payload


def branched_pipeline(condition: bool) -> int:
    """Stages: start -> (branch_a OR branch_b) -> end. Both branches must reach 'end'."""
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
    __archtest__: Annotated[None, enforce_flow(["start", "end"])]  # noqa: F811
    return counter
