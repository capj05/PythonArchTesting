"""Fully correct model implementation."""


class SubmissionRecord:
    """Base entity used by nominal subclass checks."""


class DraftSubmission(SubmissionRecord):
    """Model that satisfies all class-focused rules."""

    def __init__(self, submission_id: str, title: str) -> None:
        self.submission_id = submission_id
        self.title: str = title
