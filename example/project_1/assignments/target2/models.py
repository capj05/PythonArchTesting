"""Model implementation with incompatible annotations."""


class SubmissionRecord:
    """Base entity kept correct so nominal matching succeeds."""


class DraftSubmission(SubmissionRecord):
    """Model kept structurally similar while annotations are intentionally wrong."""

    def __init__(self, submission_id: int, title: int) -> None:
        self.submission_id = submission_id
        self.title: int = title
