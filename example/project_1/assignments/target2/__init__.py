"""Target 2 keeps the same shape but uses incompatible annotations."""

from .contracts import SubmissionRepository
from .models import DraftSubmission, SubmissionRecord
from .storage import MemorySubmissionRepository
from .workflow import SubmissionService, normalize_submission, prepare_repository

__all__ = [
    "DraftSubmission",
    "MemorySubmissionRepository",
    "SubmissionRecord",
    "SubmissionRepository",
    "SubmissionService",
    "normalize_submission",
    "prepare_repository",
]
