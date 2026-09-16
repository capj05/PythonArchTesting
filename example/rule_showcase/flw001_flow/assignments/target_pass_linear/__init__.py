"""target_pass_linear — both pipelines preserve the declared stage order."""

from .pipelines import branched_pipeline, linear_pipeline

__all__ = ["branched_pipeline", "linear_pipeline"]
