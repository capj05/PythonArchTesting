"""Fully correct workflow implementation."""

from typing import Annotated

from pythonarchtesting.rules import flow

from .contracts import SubmissionRepository
from .storage.repository import MemorySubmissionRepository


def normalize_submission(
    submission_id: str,
    title: str,
    status: str = "draft",
) -> dict[str, str]:
    """Normalize user input into a canonical payload."""
    normalized_title = title
    __archtest__: Annotated[  # noqa: F842
        None,
        flow("raw", variable="normalized_title"),
    ]
    normalized_title = normalized_title.strip()
    __archtest__: Annotated[  # noqa: F842
        None,
        flow("validated", variable="normalized_title"),
    ]
    return {
        "submission_id": submission_id.strip(),
        "title": normalized_title,
        "status": status.strip().lower(),
    }


def prepare_repository(
    repo: MemorySubmissionRepository,
) -> MemorySubmissionRepository:
    """Pass through a repository that satisfies the expected protocol."""
    return repo


class SubmissionService:
    """Service layer for saving and publishing submissions."""

    def save_draft(
        self,
        repo: SubmissionRepository,
        submission: dict[str, str],
    ) -> None:
        repo.save(submission["submission_id"], submission)

    def publish(
        self,
        repo: SubmissionRepository,
        submission_id: str,
    ) -> dict[str, str]:
        saved = repo.load(submission_id)
        return {
            **saved,
            "status": "published",
        }
