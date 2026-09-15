"""Protocol copy used by the signature-mismatch target."""

from typing import Protocol


class SubmissionRepository(Protocol):
    """Persistence API expected by the service layer."""

    def save(self, submission_id: str, payload: dict[str, str]) -> None:
        """Store one submission payload."""

    def load(self, submission_id: str) -> dict[str, str]:
        """Load one submission payload."""
