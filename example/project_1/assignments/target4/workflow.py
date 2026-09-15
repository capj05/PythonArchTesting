"""Alternative naming used to demonstrate matching diagnostics."""

from .contracts import SubmissionRepository
from .storage.repository import MemorySubmissionRepository


def prepare_repo_adapter(
    repo: MemorySubmissionRepository,
) -> MemorySubmissionRepository:
    """Do the right work under a different function name."""
    return repo


class SubmissionWorkflow:
    """Use similar semantics but non-canonical names."""

    def save_submission_draft(
        self,
        repo: SubmissionRepository,
        submission: dict[str, str],
    ) -> None:
        repo.save(submission["submission_id"], submission)

    def publish_submission_now(
        self,
        repo: SubmissionRepository,
        submission_id: str,
    ) -> dict[str, str]:
        saved = repo.load(submission_id)
        return {
            **saved,
            "status": "published",
        }
