"""
Tests for matching-stage candidate caps and memoization hooks.
"""

import textwrap
from pathlib import Path

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import MatchingConfig, run_matching


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


def test_stage2_cap_reduces_ast_similarity_calls(monkeypatch):
    root_source = Path.cwd() / "source_caps"
    root_target = Path.cwd() / "target_caps"

    source_entities = _extract(
        """
        def ref_fn(x):
            return x
        """,
        root_source / "pkg" / "pythonarchtesting.py",
        root_source,
        "source",
    )

    target_entities = []
    for idx in range(12):
        target_entities.extend(
            _extract(
                f"""
                def target_{idx}(x):
                    return x + {idx}
                """,
                root_target / "pkg" / f"t{idx}.py",
                root_target,
                "target",
            )
        )

    source_index = build_entity_index(source_entities)
    target_index = build_entity_index(target_entities)

    import pythonarchtesting.matching as matching_module

    real_ast_similarity = matching_module.ast_similarity
    calls = {"count": 0}

    def _counted_ast_similarity(source, target):
        calls["count"] += 1
        return real_ast_similarity(source, target)

    monkeypatch.setattr(matching_module, "ast_similarity", _counted_ast_similarity)

    uncapped = MatchingConfig(
        threshold=0.80,
        delta=0.03,
        min_candidate=0.0,
        top_n=5,
        max_fuzzy_candidates=1,
        max_stage2_candidates=0,
        max_stage3_candidates=0,
    )
    run_matching(source_index, target_index, uncapped)
    uncapped_calls = calls["count"]

    calls["count"] = 0
    capped = MatchingConfig(
        threshold=0.80,
        delta=0.03,
        min_candidate=0.0,
        top_n=5,
        max_fuzzy_candidates=1,
        max_stage2_candidates=2,
        max_stage3_candidates=0,
    )
    run_matching(source_index, target_index, capped)
    capped_calls = calls["count"]

    assert uncapped_calls > capped_calls
    assert capped_calls <= 2


def test_matching_config_reads_stage_caps_from_config():
    cfg = create_config_from_dict(
        {
            "matching": {
                "max_stage2_candidates": "7",
                "max_stage3_candidates": "9",
            }
        }
    )

    matching_cfg = MatchingConfig.from_config(cfg)
    assert matching_cfg.max_stage2_candidates == 7
    assert matching_cfg.max_stage3_candidates == 9
