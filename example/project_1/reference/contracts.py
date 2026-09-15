"""Protocol definitions for the reference submission workflow."""

from typing import Protocol


class SubmissionRepository(Protocol):
    """Persistence API used by the workflow showcase."""

    def save(self, submission_id: str, payload: dict[str, str]) -> None:
        """Store one submission payload."""

    def load(self, submission_id: str) -> dict[str, str]:
        """Load one submission payload."""
