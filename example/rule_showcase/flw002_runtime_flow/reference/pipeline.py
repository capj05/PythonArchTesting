"""Reference for the FLW002 runtime ``enforce_flow`` showcase.

The ``flow(...)`` markers label the stages a record passes through, exactly as
in the static FLW001 showcase. Adding ``cases=`` to ``enforce_flow`` turns the
check into a runtime one: with ``--dynamic`` the reference runs on each case
and records which of the project's functions each stage calls (``parse``,
``validate``, ``enrich``, ``store``); the target then runs the same case and
has to call them in the same stage order. Values are never compared, so a
target whose steps compute something else still passes. Targets need no
markers.

The first stage, ``received``, calls no project function: it cannot be told
apart in a target, and the result says it was not checked.
"""

from __future__ import annotations

from typing import Annotated, Any

from pythonarchtesting.rules import enforce_flow, flow

from . import steps


def import_record(line: str, sink: list[dict[str, Any]]) -> Any:
    record: Any = line
    __archtest__: Annotated[None, flow("received", variable="record")]
    record = steps.parse(record)
    __archtest__: Annotated[None, flow("parsed", variable="record")]  # noqa: F811
    record = steps.validate(record)
    __archtest__: Annotated[None, flow("validated", variable="record")]  # noqa: F811
    record = steps.enrich(record)
    __archtest__: Annotated[None, flow("enriched", variable="record")]  # noqa: F811
    steps.store(record, sink)
    __archtest__: Annotated[None, flow("stored", variable="record")]  # noqa: F811
    __archtest__: Annotated[  # noqa: F811
        None,
        enforce_flow(
            ["received", "parsed", "validated", "enriched", "stored"],
            variable="record",
            cases=[{"args": ["ada;36", []]}],
        ),
    ]
    return record
