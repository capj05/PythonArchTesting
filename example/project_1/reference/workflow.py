"""Workflow entities used to demonstrate signature and method rules."""

from typing import Annotated

from pythonarchtesting.rules import (
    enforce_flow,
    flow,
    implements_protocol,
    required_entity_signature,
    required_method,
)

from .contracts import SubmissionRepository


def normalize_submission(
    submission_id: str,
    title: str,
    status: str = "draft",
) -> Annotated[
    dict[str, str],
    required_entity_signature(mode="compatible", return_annotation="warning"),
]:
    """Normalize user input into a predictable payload."""
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
    __archtest__: Annotated[
        None,
        enforce_flow(["raw", "validated"], variable="normalized_title"),
    ]  # noqa: F842
    return {
        "submission_id": submission_id.strip(),
        "title": normalized_title,
        "status": status.strip().lower(),
    }


def prepare_repository(
    repo: Annotated[
        object,
        implements_protocol("contracts.SubmissionRepository"),
    ],
) -> Annotated[
    object,
    implements_protocol("contracts.SubmissionRepository"),
]:
    """Return a repository object after the protocol check has matched it."""
    return repo


class SubmissionService:
    """Service methods used by required-method checks."""

    def save_draft(
        self,
        repo: SubmissionRepository,
        submission: dict[str, str],
    ) -> None:
        __archtest__: Annotated[  # noqa: F842
            None,
            required_method(signature_mode="compatible"),
        ]
        repo.save(submission["submission_id"], submission)

    def publish(
        self,
        repo: SubmissionRepository,
        submission_id: str,
    ) -> dict[str, str]:
        __archtest__: Annotated[  # noqa: F842
            None,
            required_method(signature_mode="compatible"),
        ]
        saved = repo.load(submission_id)
        return {
            **saved,
            "status": "published",
        }
