"""Repository implementations for the protocol-failure target."""

from .helpers import touch_requests_dependency


class BrokenRepository:
    """Concrete type used to fail signature-level protocol checks."""

    def save(self, submission_id: str, payload: dict[str, str]) -> None:
        _ = submission_id, payload


class MemorySubmissionRepository:
    """Repository with a missing protocol method."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, str]] = {}

    def save(self, submission_id: str, payload: dict[str, str]) -> None:
        touch_requests_dependency()
        self._items[submission_id] = dict(payload)

    def fetch(self, submission_id: str) -> dict[str, str]:
        return dict(self._items[submission_id])
