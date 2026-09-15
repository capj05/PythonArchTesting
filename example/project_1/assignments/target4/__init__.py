"""Target 4 uses alternative names to stress matching diagnostics."""

from .contracts import SubmissionRepository
from .models import DraftSubmission, SubmissionRecord
from .storage import MemorySubmissionRepository
from .workflow import SubmissionWorkflow, prepare_repo_adapter

__all__ = [
    "DraftSubmission",
    "MemorySubmissionRepository",
    "SubmissionRecord",
    "SubmissionRepository",
    "SubmissionWorkflow",
    "prepare_repo_adapter",
]
