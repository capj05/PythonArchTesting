"""Correct repository implementation for the matching target."""


class MemorySubmissionRepository:
    """Repository that satisfies the submission protocol."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, str]] = {}

    def save(self, submission_id: str, payload: dict[str, str]) -> None:
        self._items[submission_id] = dict(payload)

    def load(self, submission_id: str) -> dict[str, str]:
        return dict(self._items[submission_id])
