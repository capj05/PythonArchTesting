"""Repository implementation used for the protocol showcase."""

from typing import Annotated

from pythonarchtesting.rules import implements_protocol


class MemorySubmissionRepository:
    """In-memory repository that satisfies the reference protocol."""

    __archtest__: Annotated[
        None,
        implements_protocol("contracts.SubmissionRepository"),
    ]

    def __init__(self) -> None:
        self._items: dict[str, dict[str, str]] = {}

    def save(self, submission_id: str, payload: dict[str, str]) -> None:
        self._items[submission_id] = dict(payload)

    def load(self, submission_id: str) -> dict[str, str]:
        return dict(self._items[submission_id])
