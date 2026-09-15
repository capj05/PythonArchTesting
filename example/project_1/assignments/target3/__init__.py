"""Target 3 demonstrates protocol and import-policy failures."""

from .contracts import SubmissionRepository
from .models import DraftSubmission, SubmissionRecord
from .storage import BrokenRepository, MemorySubmissionRepository
from .workflow import SubmissionService, normalize_submission, prepare_repository

__all__ = [
    "BrokenRepository",
    "DraftSubmission",
    "MemorySubmissionRepository",
    "SubmissionRecord",
    "SubmissionRepository",
    "SubmissionService",
    "normalize_submission",
    "prepare_repository",
]
