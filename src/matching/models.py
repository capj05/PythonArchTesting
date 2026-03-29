from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.config.accessors import get_float, get_int


class MatchStatus(str, Enum):
    MATCHED = "matched"
    UNMATCHED = "unmatched"
    AMBIGUOUS = "ambiguous"
    LOW_CONFIDENCE = "low_confidence"


@dataclass(frozen=True)
class Candidate:
    target_id: str
    confidence: float
    breakdown: Dict[str, float]
    tie_break: Tuple[Any, ...]


@dataclass(frozen=True)
class MatchResult:
    source_id: str
    status: MatchStatus
    target_id: Optional[str]
    confidence: float
    reasons: List[Dict[str, Any]]
    candidates: List[Candidate]


@dataclass
class MatchingConfig:
    threshold: float
    delta: float
    min_candidate: float
    top_n: int
    max_fuzzy_candidates: int
    max_stage2_candidates: int = 0
    max_stage3_candidates: int = 0

    @classmethod
    def from_config(cls, config: Any | None = None) -> "MatchingConfig":
        if config is None:
            # Backward compatibility for legacy callers.
            from src.config import load_config

            config = load_config()
        return cls(
            threshold=get_float(config, "matching", "threshold", 0.80),
            delta=get_float(config, "matching", "delta", 0.03),
            min_candidate=get_float(config, "matching", "min_candidate", 0.50),
            top_n=get_int(config, "matching", "top_n", 5),
            max_fuzzy_candidates=get_int(config, "matching", "max_fuzzy_candidates", 5),
            max_stage2_candidates=get_int(
                config, "matching", "max_stage2_candidates", 0
            ),
            max_stage3_candidates=get_int(
                config, "matching", "max_stage3_candidates", 0
            ),
        )


__all__ = ["MatchStatus", "Candidate", "MatchResult", "MatchingConfig"]
