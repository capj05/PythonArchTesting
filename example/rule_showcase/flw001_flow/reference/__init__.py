"""Reference module for the FLW001 flow / enforce_flow showcase."""

from .pipelines import branched_pipeline, linear_pipeline

__all__ = [
    "branched_pipeline",
    "linear_pipeline",
]
