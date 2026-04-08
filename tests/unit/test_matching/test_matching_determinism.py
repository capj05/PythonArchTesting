"""
Tests for deterministic matching.
"""

import textwrap
from pathlib import Path

from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import MatchingConfig, MatchStatus, run_matching


def test_matching_determinism() -> None:
    root_source = Path.cwd() / "source"
    root_target = Path.cwd() / "target"

    source_entities = extract_entities_from_source(
        textwrap.dedent("""
            def parse_data(x):
                return x
            """).strip() + "\n",
        root_source / "pkg" / "mod.py",
        root_source,
        None,
        role="source",
        include_nested_functions=False,
    )
    target_entities = []
    target_entities.extend(
        extract_entities_from_source(
            textwrap.dedent("""
                def parse_data_v1(x):
                    return x
                """).strip() + "\n",
            root_target / "pkg" / "a.py",
            root_target,
            None,
            role="target",
            include_nested_functions=False,
        )
    )
    target_entities.extend(
        extract_entities_from_source(
            textwrap.dedent("""
                def parse_data_v2(x):
                    return x
                """).strip() + "\n",
            root_target / "pkg" / "b.py",
            root_target,
            None,
            role="target",
            include_nested_functions=False,
        )
    )

    source_entities = [entity for entity in source_entities if entity.kind != "module"]
    target_entities = [entity for entity in target_entities if entity.kind != "module"]

    source_index = build_entity_index(source_entities)
    target_index = build_entity_index(target_entities)
    config = MatchingConfig.from_config()

    _, first_by_source = run_matching(source_index, target_index, config)
    _, second_by_source = run_matching(source_index, target_index, config)

    source_id = source_entities[0].canonical_id
    first = first_by_source[source_id]
    second = second_by_source[source_id]

    assert first.status == second.status
    assert first.confidence == second.confidence
    assert first.candidates == second.candidates
    assert first.status == MatchStatus.LOW_CONFIDENCE
