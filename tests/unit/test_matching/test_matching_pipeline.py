"""
Tests for matching pipeline behaviors.
"""

import textwrap
from pathlib import Path

from src.entities import build_entity_index
from src.entities_extraction import extract_entities_from_source
from src.matching import MatchingConfig, MatchStatus, run_matching
from src.matching.metrics import module_distance, name_similarity
from src.state import ProjectState


def _extract(source: str, file_path: Path, root_path: Path, role: str) -> list:
    entities = extract_entities_from_source(
        textwrap.dedent(source).strip() + "\n",
        file_path,
        root_path,
        None,
        role=role,
        include_nested_functions=False,
    )
    return [entity for entity in entities if entity.kind != "module"]


def test_method_first_param_mismatch_penalty() -> None:
    root_source = Path.cwd() / "source_method"
    root_target = Path.cwd() / "target_method"

    source_entities = _extract(
        """
        class C:
            def m(self, x):
                return x
        """,
        root_source / "mod.py",
        root_source,
        "source",
    )
    target_entities = _extract(
        """
        class C:
            def m(x):
                return x
        """,
        root_target / "mod.py",
        root_target,
        "target",
    )

    source_index = build_entity_index(source_entities)
    target_index = build_entity_index(target_entities)
    config = MatchingConfig(
        threshold=0.80,
        delta=0.03,
        min_candidate=0.50,
        top_n=5,
        max_fuzzy_candidates=5,
    )

    _, by_source = run_matching(source_index, target_index, config)
    source_method = next(e for e in source_entities if e.kind == "method")
    match = by_source[source_method.canonical_id]
    candidate = match.candidates[0]

    expected = round(0.55 * 1.0 + 0.30 * 1.0 + 0.15 * 0.0 - 0.03, 6)
    assert abs(candidate.breakdown.get("penalty", 0.0) - 0.03) < 1e-6
    assert candidate.confidence == expected


def test_explicit_target_match() -> None:
    root_source = Path.cwd() / "source_explicit"
    root_target = Path.cwd() / "target_explicit"

    source_entities = _extract(
        """
        def source_fn(x):
            return x
        """,
        root_source / "src_mod.py",
        root_source,
        "source",
    )
    target_entities = _extract(
        """
        def target_fn(x):
            return x
        """,
        root_target / "target_mod.py",
        root_target,
        "target",
    )

    source_entity = source_entities[0]
    target_entity = target_entities[0]
    source_entity.decorators_meta["explicit_target"] = {
        "module_path": target_entity.module_path,
        "qualname": target_entity.qualname,
        "kind": target_entity.kind,
        "signature_key": target_entity.signature_key,
    }

    source_index = build_entity_index(source_entities)
    target_index = build_entity_index(target_entities)
    config = MatchingConfig.from_config()

    _, by_source = run_matching(source_index, target_index, config)
    match = by_source[source_entity.canonical_id]

    assert match.status == MatchStatus.MATCHED
    assert match.target_id == target_entity.canonical_id
    assert any(reason.get("code") == "explicit_target_hit" for reason in match.reasons)
    assert match.candidates[0].breakdown["name"] == name_similarity(
        source_entity.name, target_entity.name
    )
    assert match.candidates[0].breakdown["module_distance"] == float(
        module_distance(source_entity.module_path, target_entity.module_path)
    )


def test_stage1_exact_breakdown_includes_name_and_raw_module_distance() -> None:
    root_source = Path.cwd() / "source_stage1_exact"
    root_target = Path.cwd() / "target_stage1_exact"

    source_entities = _extract(
        """
        def same_name(x):
            return x
        """,
        root_source / "pkg" / "mod.py",
        root_source,
        "source",
    )
    target_entities = _extract(
        """
        def same_name(x):
            return x
        """,
        root_target / "pkg" / "mod.py",
        root_target,
        "target",
    )

    source_index = build_entity_index(source_entities)
    target_index = build_entity_index(target_entities)
    config = MatchingConfig.from_config()

    _, by_source = run_matching(source_index, target_index, config)
    match = by_source[source_entities[0].canonical_id]
    candidate = match.candidates[0]

    assert any(reason.get("code") == "stage1_exact" for reason in match.reasons)
    assert candidate.breakdown["name"] == 1.0
    assert candidate.breakdown["module_distance"] == 0.0


def test_stage2_breakdown_includes_real_name_similarity() -> None:
    root_source = Path.cwd() / "source_stage2_name"
    root_target = Path.cwd() / "target_stage2_name"

    source_entities = _extract(
        """
        def parse_data(x):
            return x
        """,
        root_source / "pkg" / "src.py",
        root_source,
        "source",
    )
    target_entities = _extract(
        """
        def parse_data_v1(x):
            return x
        """,
        root_target / "pkg" / "tgt.py",
        root_target,
        "target",
    )

    source_index = build_entity_index(source_entities)
    target_index = build_entity_index(target_entities)
    config = MatchingConfig(
        threshold=0.95,
        delta=0.03,
        min_candidate=0.0,
        top_n=5,
        max_fuzzy_candidates=5,
    )

    _, by_source = run_matching(source_index, target_index, config)
    match = by_source[source_entities[0].canonical_id]
    candidate = match.candidates[0]
    expected = name_similarity(source_entities[0].name, target_entities[0].name)

    assert any(reason.get("code") == "stage3_not_run" for reason in match.reasons)
    assert candidate.breakdown["name"] == expected
    assert 0.0 < candidate.breakdown["name"] < 1.0


def test_legacy_fallback_audit() -> None:
    state = ProjectState("/test", [])

    root_source = Path.cwd() / "source_legacy"
    root_target = Path.cwd() / "target_legacy"

    source_entities = _extract(
        """
        def f(x):
            return x
        """,
        root_source / "legacy_src.py",
        root_source,
        "source",
    )
    target_entities = _extract(
        """
        def f(x, y):
            return x
        """,
        root_target / "legacy_tgt.py",
        root_target,
        "target",
    )

    source_index = build_entity_index(source_entities)
    target_index = build_entity_index(target_entities)
    config = MatchingConfig(
        threshold=0.99,
        delta=0.03,
        min_candidate=0.99,
        top_n=5,
        max_fuzzy_candidates=5,
    )

    results, by_source = run_matching(source_index, target_index, config)
    state.target_index = target_index
    state.source_by_id = {e.canonical_id: e for e in source_entities}

    _, updated_by_source = state._apply_legacy_fallback(results, by_source, config)
    match = updated_by_source[source_entities[0].canonical_id]

    assert match.status == MatchStatus.UNMATCHED
    assert any(reason.get("code") == "legacy_fallback_used" for reason in match.reasons)

    legacy_candidates = [
        candidate
        for candidate in match.candidates
        if candidate.breakdown.get("legacy_name_match") == 1.0
    ]
    assert legacy_candidates
    assert all(candidate.confidence <= 0.60 + 1e-6 for candidate in legacy_candidates)


def test_stage3_selected_on_ambiguous_stage2() -> None:
    root_source = Path.cwd() / "source_stage3"
    root_target = Path.cwd() / "target_stage3"

    source_entities = _extract(
        """
        def f(x):
            "doc"
            return x
        """,
        root_source / "pkg" / "mod.py",
        root_source,
        "source",
    )
    target_entities = []
    target_entities.extend(
        _extract(
            """
            def f(x):
                "doc"
                return x
            """,
            root_target / "pkg" / "mod1.py",
            root_target,
            "target",
        )
    )
    target_entities.extend(
        _extract(
            """
            def f(x):
                "doc"
                return x
            """,
            root_target / "pkg" / "mod2.py",
            root_target,
            "target",
        )
    )

    source_index = build_entity_index(source_entities)
    target_index = build_entity_index(target_entities)
    config = MatchingConfig.from_config()

    _, by_source = run_matching(source_index, target_index, config)
    match = by_source[source_entities[0].canonical_id]
    assert any(reason.get("code") == "stage3_selected" for reason in match.reasons)


def test_ambiguous_status_with_competitor_within_delta() -> None:
    root_source = Path.cwd() / "source_ambig"
    root_target = Path.cwd() / "target_ambig"

    source_entities = _extract(
        """
        def g(x):
            "doc"
            return x
        """,
        root_source / "pkg" / "mod.py",
        root_source,
        "source",
    )
    target_entities = []
    target_entities.extend(
        _extract(
            """
            def g(x):
                "doc"
                return x
            """,
            root_target / "pkg" / "mod1.py",
            root_target,
            "target",
        )
    )
    target_entities.extend(
        _extract(
            """
            def g(x):
                "doc"
                return x
            """,
            root_target / "pkg" / "mod2.py",
            root_target,
            "target",
        )
    )

    source_index = build_entity_index(source_entities)
    target_index = build_entity_index(target_entities)
    config = MatchingConfig.from_config()

    _, by_source = run_matching(source_index, target_index, config)
    match = by_source[source_entities[0].canonical_id]

    assert match.status == MatchStatus.AMBIGUOUS
    assert any(
        reason.get("code") == "ambiguous_competitor_within_delta"
        for reason in match.reasons
    )


def test_explicit_target_missing_fields_reason() -> None:
    root_source = Path.cwd() / "source_explicit_missing"
    source_entities = _extract(
        """
        def h(x):
            return x
        """,
        root_source / "pkg" / "mod.py",
        root_source,
        "source",
    )
    source_entity = source_entities[0]
    source_entity.decorators_meta["explicit_target"] = {"module_path": "pkg.mod"}

    source_index = build_entity_index(source_entities)
    target_index = build_entity_index([])
    config = MatchingConfig.from_config()

    _, by_source = run_matching(source_index, target_index, config)
    match = by_source[source_entity.canonical_id]
    assert any(
        reason.get("code") == "explicit_target_not_found" for reason in match.reasons
    )


def test_candidate_sort_tiebreaks_on_module_distance() -> None:
    root_source = Path.cwd() / "source_tiebreak"
    root_target = Path.cwd() / "target_tiebreak"

    source_entities = _extract(
        """
        def k(x):
            return x
        """,
        root_source / "pkg" / "sub" / "mod" / "a.py",
        root_source,
        "source",
    )
    target_entities = []
    target_entities.extend(
        _extract(
            """
            def k(x):
                return x
            """,
            root_target / "pkg" / "sub.py",
            root_target,
            "target",
        )
    )
    target_entities.extend(
        _extract(
            """
            def k(x):
                return x
            """,
            root_target / "pkg" / "sub" / "mod" / "extra" / "deeper" / "more.py",
            root_target,
            "target",
        )
    )

    source_index = build_entity_index(source_entities)
    target_index = build_entity_index(target_entities)
    config = MatchingConfig.from_config()

    _, by_source = run_matching(source_index, target_index, config)
    match = by_source[source_entities[0].canonical_id]
    assert len(match.candidates) >= 2
    assert (
        match.candidates[0].breakdown["module_distance"]
        <= match.candidates[1].breakdown["module_distance"]
    )
