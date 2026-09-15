"""Skeletal workflow with only one implemented service method."""

from .contracts import SubmissionRepository


class SubmissionService:
    """Partial implementation used to showcase missing entities."""

    def save_draft(
        self,
        repo: SubmissionRepository,
        submission: dict[str, str],
    ) -> None:
        repo.save(submission["submission_id"], submission)
