from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import Mock

from src.entities_extraction import extract_entities_from_source
from src.rules.compilation import compile_rules
from src.rules.compilation.declarations import (
    declaration_rule_id_suffixes,
    normalize_declaration_entries,
)


def _extract_entities(source: str):
    return extract_entities_from_source(
        textwrap.dedent(source).strip() + "\n",
        Path("sample.py"),
        Path("."),
        None,
        role="source",
        include_nested_functions=False,
    )


def test_normalize_annotation_only_entries() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import required_entity_signature, required_method

        def run(value: int) -> int:
            __archtest__: Annotated[
                None,
                required_method(signature_mode="exact"),
                required_entity_signature(mode="compatible"),
            ]
            return value
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")
    entries = normalize_declaration_entries(function_entity)

    assert [entry.kind for entry in entries] == [
        "required_method",
        "required_entity_signature",
    ]
    assert all(entry.container == "Annotated" for entry in entries)
    assert all(entry.base_annotation == "None" for entry in entries)
    assert entries[0].params == {"signature_mode": "exact"}


def test_normalize_same_annotation_keeps_one_entry() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import required_entity_signature

        def run(value: int) -> int:
            __archtest__: Annotated[None, required_entity_signature(mode="exact")]
            __archtest__: Annotated[None, required_entity_signature(mode="exact")]
            return value
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")
    entries = normalize_declaration_entries(function_entity)

    assert len(entries) == 1
    assert entries[0].kind == "required_entity_signature"
    assert entries[0].params["mode"] == "exact"


def test_normalize_same_kind_annotations_keep_stable_order_and_suffixes() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import required_entity_signature

        def run(value: int) -> int:
            __archtest__: Annotated[None, required_entity_signature(mode="compatible")]
            __archtest__: Annotated[None, required_entity_signature(mode="exact")]
            return value
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")
    entries = normalize_declaration_entries(function_entity)

    assert [entry.params["mode"] for entry in entries] == ["compatible", "exact"]
    assert declaration_rule_id_suffixes(entries) == ["/d0", "/d1"]


def test_invalid_annotation_declarations_emit_compiler_evidence_without_rules() -> None:
    entities = _extract_entities("""
        from typing import Annotated

        def run(value: int) -> int:
            __archtest__: Annotated[None, "custom"]
            return value
        """)
    function_entity = next(entity for entity in entities if entity.kind == "function")

    rules, evidence, compiler_results = compile_rules([function_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_required_signature_annotation_declaration_compiles_supported_rules() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import required_entity_signature

        def run(value: int) -> int:
            __archtest__: Annotated[
                None,
                required_entity_signature(mode="compatible", return_annotation="warning"),
            ]
            return value
        """)
    function_entity = next(entity for entity in entities if entity.kind == "function")

    rules, evidence, compiler_results = compile_rules([function_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == [
        "API001/required_entity_signature/v1",
        "API001/required_entity_signature_return/v1",
    ]


def test_multiple_same_kind_annotation_declarations_get_unique_rule_ids() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import required_entity_signature

        def run(value: int) -> int:
            __archtest__: Annotated[
                None,
                required_entity_signature(mode="compatible", return_annotation="warning"),
            ]
            __archtest__: Annotated[
                None,
                required_entity_signature(mode="exact", return_annotation="warning"),
            ]
            return value
        """)
    function_entity = next(entity for entity in entities if entity.kind == "function")

    rules, evidence, compiler_results = compile_rules([function_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == [
        "API001/required_entity_signature/v1/d0",
        "API001/required_entity_signature/v1/d1",
        "API001/required_entity_signature_return/v1/d0",
        "API001/required_entity_signature_return/v1/d1",
    ]


def test_normalize_same_signature_annotation_keeps_one_entry() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import required_entity_signature

        def run(
            value: Annotated[int, required_entity_signature(mode="exact")],
        ) -> Annotated[int, required_entity_signature(mode="exact")]:
            return value
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")
    entries = normalize_declaration_entries(function_entity)

    assert len(entries) == 2
    assert [entry.kind for entry in entries] == [
        "required_entity_signature",
        "required_entity_signature",
    ]
    assert [(entry.subject_kind, entry.subject_index) for entry in entries] == [
        ("param", 0),
        ("return", -1),
    ]


def test_literal_and_marker_metadata_normalize_to_same_entry() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import required_entity_signature

        def run(value: int) -> int:
            __archtest__: Annotated[
                None,
                ("required_entity_signature", {"mode": "exact"}),
            ]
            __archtest__: Annotated[None, required_entity_signature(mode="exact")]
            return value
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")
    entries = normalize_declaration_entries(function_entity)

    assert len(entries) == 1
    assert entries[0].kind == "required_entity_signature"
    assert entries[0].params["mode"] == "exact"


def test_literal_signature_annotation_declaration_compiles_supported_rules() -> None:
    entities = _extract_entities("""
        from typing import Annotated

        def run(
            value: Annotated[
                int,
                (
                    "required_entity_signature",
                    {"mode": "compatible", "return_annotation": "warning"},
                ),
            ],
        ) -> int:
            return value
        """)
    function_entity = next(entity for entity in entities if entity.kind == "function")

    rules, evidence, compiler_results = compile_rules([function_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == [
        "API001/required_entity_signature/v1",
        "API001/required_entity_signature_return/v1",
    ]


def test_invalid_literal_annotation_declarations_emit_compiler_evidence_without_rules() -> (
    None
):
    entities = _extract_entities("""
        from typing import Annotated

        def run(value: int) -> int:
            __archtest__: Annotated[None, ("required_entity_signature", ["exact"])]
            return value
        """)
    function_entity = next(entity for entity in entities if entity.kind == "function")

    rules, evidence, compiler_results = compile_rules([function_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_signature_required_signature_annotation_declaration_compiles_supported_rules() -> (
    None
):
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import required_entity_signature

        def run(
            value: Annotated[
                int,
                required_entity_signature(mode="compatible", return_annotation="warning"),
            ],
        ) -> int:
            return value
        """)
    function_entity = next(entity for entity in entities if entity.kind == "function")

    rules, evidence, compiler_results = compile_rules([function_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == [
        "API001/required_entity_signature/v1",
        "API001/required_entity_signature_return/v1",
    ]


def test_removed_type_check_signature_rule_kind_emits_invalid_declaration_evidence() -> (
    None
):
    entities = _extract_entities("""
        from typing import Annotated

        def run(
            value: Annotated[int, ("type_check", {"strict": True})],
        ) -> int:
            return value
        """)
    function_entity = next(entity for entity in entities if entity.kind == "function")

    rules, evidence, compiler_results = compile_rules([function_entity], Mock())

    assert rules == []
    assert evidence == []
    assert compiler_results == []


def test_signature_disallowed_rule_kind_emits_invalid_declaration_evidence() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import forbid_imports

        def run(
            value: Annotated[int, forbid_imports("requests", scope="entity")],
        ) -> int:
            return value
        """)
    function_entity = next(entity for entity in entities if entity.kind == "function")

    rules, evidence, compiler_results = compile_rules([function_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_protocol_signature_rule_kind_compiles_protocol_signature_rule() -> None:
    entities = _extract_entities("""
        from typing import Annotated, Protocol
        from src.rules import implements_protocol

        class Repository(Protocol):
            def get(self, item_id: str) -> str:
                ...

        def run(
            value: Annotated[int, implements_protocol(Repository)],
        ) -> int:
            return value
        """)
    rules, evidence, compiler_results = compile_rules(entities, Mock())

    assert [rule.rule_id for rule in rules] == [
        "PRO002/implements_protocol_signature/v1"
    ]
    assert compiler_results == []
    assert evidence == []


def test_protocol_signature_symbol_reference_missing_emits_compiler_evidence() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import implements_protocol

        def run(
            value: Annotated[int, implements_protocol(Repository)],
        ) -> int:
            return value
        """)

    rules, evidence, compiler_results = compile_rules(entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_protocol_reference"]


def test_compile_rules_surface_matches_supported_canonical_import() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import required_method

        def run(value: int) -> int:
            __archtest__: Annotated[None, required_method(signature_mode="exact")]
            return value
        """)
    function_entity = next(entity for entity in entities if entity.kind == "function")

    canonical = compile_rules([function_entity], Mock())
    direct = compile_rules([function_entity], Mock())

    assert [rule.rule_id for rule in canonical[0]] == [
        rule.rule_id for rule in direct[0]
    ]
    assert [item.type for item in canonical[1]] == [item.type for item in direct[1]]
    assert [result.rule_id for result in canonical[2]] == [
        result.rule_id for result in direct[2]
    ]


def test_flow_declarations_are_preserved_without_deduping_and_enforce_flow_compiles() -> (
    None
):
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import enforce_flow, flow

        def run(value: str) -> str:
            current = value
            __archtest__: Annotated[None, flow("raw")]
            current = current.strip()
            __archtest__: Annotated[None, flow("validated")]
            __archtest__: Annotated[None, enforce_flow(["raw", "validated"])]
            return current
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")
    entries = normalize_declaration_entries(function_entity)
    assert [entry.kind for entry in entries] == ["flow", "flow", "enforce_flow"]

    rules, evidence, compiler_results = compile_rules([function_entity], Mock())
    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["FLW001/enforce_flow/v1"]


def test_enforce_flow_without_explicit_variable_emits_ambiguity_evidence() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import enforce_flow, flow

        def run(value: str) -> str:
            first = value
            __archtest__: Annotated[None, flow("raw")]
            second = value.strip()
            __archtest__: Annotated[None, flow("validated")]
            __archtest__: Annotated[None, enforce_flow(["raw", "validated"])]
            return second
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")
    rules, evidence, compiler_results = compile_rules([function_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_flow_declaration"]
