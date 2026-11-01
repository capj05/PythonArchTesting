"""Two reference entities that pick one target: the loser's next pick."""

from __future__ import annotations

from pythonarchtesting.matching.engine import _one_to_one
from pythonarchtesting.matching.models import (
    Candidate,
    MatchingConfig,
    MatchResult,
    MatchStatus,
)

_CONFIG = MatchingConfig(
    threshold=0.7, delta=0.05, min_candidate=0.3, top_n=5, max_fuzzy_candidates=5
)


def _candidate(target: str, confidence: float) -> Candidate:
    return Candidate(target, confidence, {"name": 0.5}, ())


def _match(source: str, *candidates: Candidate) -> MatchResult:
    return MatchResult(
        source_id=source,
        status=MatchStatus.MATCHED,
        target_id=candidates[0].target_id,
        confidence=candidates[0].confidence,
        reasons=[],
        candidates=list(candidates),
    )


def test_the_losers_next_pick_is_ambiguous_when_a_rival_is_within_delta() -> None:
    winner = _match("subscribe", _candidate("t.subscribe", 0.95))
    loser = _match(
        "unsubscribe",
        _candidate("t.subscribe", 0.9),
        _candidate("t.notify", 0.81),
        _candidate("t.unsubscribe", 0.80),
    )

    _, moved = _one_to_one([winner, loser], _CONFIG)

    assert moved.status == MatchStatus.AMBIGUOUS
    assert moved.target_id == "t.notify"
    codes = [reason["code"] for reason in moved.reasons]
    assert codes == [
        "target_taken_by_better_match",
        "ambiguous_competitor_within_delta",
    ]


def test_the_losers_next_pick_is_matched_when_it_stands_out() -> None:
    winner = _match("subscribe", _candidate("t.subscribe", 0.95))
    loser = _match(
        "unsubscribe",
        _candidate("t.subscribe", 0.9),
        _candidate("t.unsubscribe", 0.85),
        _candidate("t.notify", 0.5),
    )

    _, moved = _one_to_one([winner, loser], _CONFIG)

    assert moved.status == MatchStatus.MATCHED
    assert moved.target_id == "t.unsubscribe"
