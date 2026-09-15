"""Entities used to demonstrate class-focused rule families."""

from typing import Annotated

from pythonarchtesting.rules import (
    does_not_have,
    required_attribute,
    required_constructor,
    required_factory,
    subclass_of,
)


class SubmissionRecord:
    """Base entity used by nominal subclass checks."""


class DraftSubmission(SubmissionRecord):
    """Submission model used by attribute, constructor, and factory checks."""

    __archtest__: Annotated[
        None,
        subclass_of("models.SubmissionRecord"),
        required_attribute("title", annotation="str", storage="instance"),
        required_constructor(signature_mode="compatible"),
        does_not_have("debug_dump", member_kind="method"),
    ]

    def __init__(self, submission_id: str, title: str) -> None:
        __archtest__: Annotated[None, required_factory()]  # noqa: F842
        self.submission_id = submission_id
        self.title: str = title
