"""Matched workflow with intentionally incompatible annotations."""

from typing import Annotated

from pythonarchtesting.rules import flow

from .storage.repository import MemorySubmissionRepository


def normalize_submission(
    submission_id: int,
    title: int,
    status: int = 0,
) -> list[str]:
    """Return the wrong shape on purpose for the report showcase."""
    normalized_title = title
    __archtest__: Annotated[  # noqa: F842
        None,
        flow("raw", variable="normalized_title"),
    ]
    normalized_title = normalized_title + 1
    __archtest__: Annotated[  # noqa: F842
        None,
        flow("validated", variable="normalized_title"),
    ]
    return [str(submission_id), str(title), str(status)]


def prepare_repository(
    repo: MemorySubmissionRepository,
) -> MemorySubmissionRepository:
    """Keep protocol-related checks clean in this target."""
    return repo


class SubmissionService:
    """Service with the right names but wrong annotations."""

    def save_draft(
        self,
        repo: str,
        submission: list[str],
    ) -> str:
        return f"{repo}:{len(submission)}"

    def publish(
        self,
        repo: str,
        submission_id: int,
    ) -> str:
        return f"{repo}:{submission_id}"
