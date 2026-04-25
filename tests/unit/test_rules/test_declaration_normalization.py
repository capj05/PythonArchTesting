from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.rules.compilation import compile_rules
from pythonarchtesting.rules.compilation.declarations import (
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
        from pythonarchtesting.rules import required_entity_signature, required_method

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


def test_required_method_declared_only_annotation_normalizes() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import required_method

        class Processor:
            def run(self, value: int) -> int:
                __archtest__: Annotated[
                    None,
                    required_method(signature_mode="exact", declared_only=True),
                ]
                return value
        """)

    method_entity = next(entity for entity in entities if entity.kind == "method")
    entries = normalize_declaration_entries(method_entity)

    assert [entry.kind for entry in entries] == ["required_method"]
    assert entries[0].params == {
        "signature_mode": "exact",
        "declared_only": True,
    }


def test_required_method_allow_missing_annotation_normalizes() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import required_method

        class Processor:
            def run(self, value: int) -> int:
                __archtest__: Annotated[
                    None,
                    required_method(signature_mode="exact", allow_missing=True),
                ]
                return value
        """)

    method_entity = next(entity for entity in entities if entity.kind == "method")
    entries = normalize_declaration_entries(method_entity)

    assert [entry.kind for entry in entries] == ["required_method"]
    assert entries[0].params == {
        "signature_mode": "exact",
        "allow_missing": True,
    }


def test_required_method_any_signature_mode_annotation_normalizes() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import required_method

        class Processor:
            def run(self, value: int) -> int:
                __archtest__: Annotated[
                    None,
                    required_method(signature_mode="any"),
                ]
                return value
        """)

    method_entity = next(entity for entity in entities if entity.kind == "method")
    entries = normalize_declaration_entries(method_entity)

    assert [entry.kind for entry in entries] == ["required_method"]
    assert entries[0].params == {"signature_mode": "any"}


def test_required_method_flexible_name_annotation_normalizes() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import required_method

        class Processor:
            def run(self, value: int) -> int:
                __archtest__: Annotated[
                    None,
                    required_method(
                        signature_mode="compatible",
                        name_match="alias",
                        aliases=["get", "load"],
                    ),
                ]
                return value
        """)

    method_entity = next(entity for entity in entities if entity.kind == "method")
    entries = normalize_declaration_entries(method_entity)

    assert [entry.kind for entry in entries] == ["required_method"]
    assert entries[0].params == {
        "signature_mode": "compatible",
        "name_match": "alias",
        "aliases": ["get", "load"],
    }


def test_required_factory_annotation_normalizes() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import required_factory

        class Processor:
            @classmethod
            def build(cls, value: int) -> "Processor":
                __archtest__: Annotated[
                    None,
                    required_factory(
                        signature_mode="exact",
                        satisfy_with=("classmethod",),
                        allow_inherited=False,
                        allow_missing=True,
                        name_match="alias",
                        aliases=["create"],
                        return_annotation_mode="exact",
                        detection_mode="extended",
                    ),
                ]
                return cls()
        """)

    method_entity = next(entity for entity in entities if entity.kind == "method")
    entries = normalize_declaration_entries(method_entity)

    assert [entry.kind for entry in entries] == ["required_factory"]
    assert entries[0].params == {
        "signature_mode": "exact",
        "satisfy_with": ("classmethod",),
        "allow_inherited": False,
        "allow_missing": True,
        "name_match": "alias",
        "aliases": ["create"],
        "return_annotation_mode": "exact",
        "detection_mode": "extended",
    }


def test_normalize_same_annotation_keeps_one_entry() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import required_entity_signature

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
        from pythonarchtesting.rules import required_entity_signature

        def run(value: int) -> int:
            __archtest__: Annotated[None, required_entity_signature(mode="compatible")]
            __archtest__: Annotated[None, required_entity_signature(mode="exact")]
            return value
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")
    entries = normalize_declaration_entries(function_entity)

    assert [entry.params["mode"] for entry in entries] == ["compatible", "exact"]
    assert declaration_rule_id_suffixes(entries) == ["/d0", "/d1"]


def test_subclass_of_annotation_normalizes_and_dedupes() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import subclass_of

        class BaseRepository:
            pass

        class CsvRepository(BaseRepository):
            __archtest__: Annotated[None, subclass_of("sample.BaseRepository")]
            __archtest__: Annotated[None, ("subclass_of", {"base": "sample.BaseRepository"})]
        """)

    class_entity = next(
        entity
        for entity in entities
        if entity.kind == "class" and entity.name == "CsvRepository"
    )
    entries = normalize_declaration_entries(class_entity)

    assert len(entries) == 1
    assert entries[0].kind == "subclass_of"
    assert entries[0].params["base"] == "sample.BaseRepository"


def test_nominal_family_annotations_normalize_and_dedupe() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import (
            exact_type,
            inherits_directly_from,
            not_subclass_of,
        )

        class BaseRepository:
            pass

        class CsvRepository(BaseRepository):
            __archtest__: Annotated[None, exact_type("sample.BaseRepository")]
            __archtest__: Annotated[None, ("exact_type", {"base": "sample.BaseRepository"})]
            __archtest__: Annotated[None, not_subclass_of("sample.LegacyRepository")]
            __archtest__: Annotated[
                None,
                inherits_directly_from("sample.ImmediateRepositoryBase"),
            ]
        """)

    class_entity = next(
        entity
        for entity in entities
        if entity.kind == "class" and entity.name == "CsvRepository"
    )
    entries = normalize_declaration_entries(class_entity)

    assert [entry.kind for entry in entries] == [
        "exact_type",
        "not_subclass_of",
        "inherits_directly_from",
    ]
    assert entries[0].params["base"] == "sample.BaseRepository"
    assert entries[1].params["base"] == "sample.LegacyRepository"
    assert entries[2].params["base"] == "sample.ImmediateRepositoryBase"


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
        from pythonarchtesting.rules import required_entity_signature

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
        from pythonarchtesting.rules import required_entity_signature

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
        from pythonarchtesting.rules import required_entity_signature

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
        from pythonarchtesting.rules import required_entity_signature

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
        from pythonarchtesting.rules import required_entity_signature

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
        from pythonarchtesting.rules import forbid_imports

        def run(
            value: Annotated[int, forbid_imports("requests", scope="module")],
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
        from pythonarchtesting.rules import implements_protocol

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
        from pythonarchtesting.rules import implements_protocol

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
        from pythonarchtesting.rules import required_method

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


def test_required_attribute_annotation_declaration_normalizes() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import required_attribute

        class User:
            __archtest__: Annotated[
                None,
                required_attribute("email", annotation="str", storage="instance"),
            ]
        """)
    class_entity = next(entity for entity in entities if entity.kind == "class")

    entries = normalize_declaration_entries(class_entity)

    assert [entry.kind for entry in entries] == ["required_attribute"]
    assert entries[0].params == {
        "name": "email",
        "annotation": "str",
        "storage": "instance",
    }


def test_required_attribute_annotation_declaration_compiles_supported_rule() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import required_attribute

        class User:
            __archtest__: Annotated[None, required_attribute("email")]
        """)
    class_entity = next(entity for entity in entities if entity.kind == "class")

    rules, evidence, compiler_results = compile_rules([class_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == ["API003/required_attribute/v1"]


def test_multiple_required_attribute_declarations_get_unique_rule_ids() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import required_attribute

        class User:
            __archtest__: Annotated[None, required_attribute("email")]
            __archtest__: Annotated[
                None,
                required_attribute("VERSION", storage="class"),
            ]
        """)
    class_entity = next(entity for entity in entities if entity.kind == "class")

    rules, evidence, compiler_results = compile_rules([class_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == [
        "API003/required_attribute/v1/d0",
        "API003/required_attribute/v1/d1",
    ]


def test_required_attribute_allow_property_params_survive_normalization() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import required_attribute

        class User:
            __archtest__: Annotated[
                None,
                required_attribute(
                    "x",
                    allow_property=True,
                    require_writable=True,
                    declared_only=True,
                    allow_missing=True,
                ),
            ]
        """)
    class_entity = next(entity for entity in entities if entity.kind == "class")

    entries = normalize_declaration_entries(class_entity)

    assert [entry.kind for entry in entries] == ["required_attribute"]
    assert entries[0].params.get("allow_property") is True
    assert entries[0].params.get("require_writable") is True
    assert entries[0].params.get("declared_only") is True
    assert entries[0].params.get("allow_missing") is True

    rules, evidence, compiler_results = compile_rules([class_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert len(rules) == 1
    rule = rules[0]
    assert rule.rule_id == "API003/required_attribute/v1"
    assert rule.rule_type == "attribute_contract"
    assert rule.params.get("allow_property") is True
    assert rule.params.get("require_writable") is True
    assert rule.params.get("declared_only") is True
    assert rule.params.get("allow_missing") is True


def test_required_attribute_v2_params_survive_normalization() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import required_attribute

        class User:
            __archtest__: Annotated[
                None,
                required_attribute(
                    "x",
                    descriptor_kinds=("cached_property",),
                    include_dynamic_attributes=True,
                    interpret_dataclass_fields=True,
                ),
            ]
        """)
    class_entity = next(entity for entity in entities if entity.kind == "class")

    entries = normalize_declaration_entries(class_entity)

    assert [entry.kind for entry in entries] == ["required_attribute"]
    assert entries[0].params.get("descriptor_kinds") == ("cached_property",)
    assert entries[0].params.get("include_dynamic_attributes") is True
    assert entries[0].params.get("interpret_dataclass_fields") is True

    rules, evidence, compiler_results = compile_rules([class_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert len(rules) == 1
    rule = rules[0]
    assert rule.rule_id == "API003/required_attribute/v2"
    assert rule.params.get("descriptor_kinds") == ("cached_property",)
    assert rule.params.get("include_dynamic_attributes") is True
    assert rule.params.get("interpret_dataclass_fields") is True


def test_required_constructor_annotation_declaration_normalizes() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import required_constructor

        class User:
            __archtest__: Annotated[
                None,
                required_constructor(signature_mode="compatible", allow_missing=True),
            ]

            def __init__(self, name: str) -> None:
                self.name = name
        """)
    class_entity = next(entity for entity in entities if entity.kind == "class")

    entries = normalize_declaration_entries(class_entity)

    kinds = [entry.kind for entry in entries]
    assert "required_constructor" in kinds
    ctor_entry = next(e for e in entries if e.kind == "required_constructor")
    assert ctor_entry.params == {"signature_mode": "compatible", "allow_missing": True}


def test_required_constructor_annotation_declaration_compiles_supported_rule() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import required_constructor

        class User:
            __archtest__: Annotated[None, required_constructor()]

            def __init__(self, name: str) -> None:
                self.name = name
        """)

    rules, evidence, compiler_results = compile_rules(entities, Mock())

    assert evidence == []
    assert compiler_results == []
    ctor_rule_ids = [
        rule.rule_id
        for rule in rules
        if rule.rule_id.startswith("API003/required_constructor")
    ]
    assert ctor_rule_ids == ["API003/required_constructor/v1"]


def test_does_not_have_annotation_declaration_normalizes() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import does_not_have

        class User:
            __archtest__: Annotated[
                None,
                does_not_have(
                    "debug_dump",
                    member_kind="method",
                    declared_only=True,
                ),
            ]
        """)
    class_entity = next(entity for entity in entities if entity.kind == "class")

    entries = normalize_declaration_entries(class_entity)

    assert [entry.kind for entry in entries] == ["does_not_have"]
    assert entries[0].params == {
        "name": "debug_dump",
        "member_kind": "method",
        "declared_only": True,
    }


def test_normalize_same_does_not_have_annotation_keeps_one_entry() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import does_not_have

        class User:
            __archtest__: Annotated[
                None,
                does_not_have("debug_dump", member_kind="method"),
            ]
            __archtest__: Annotated[
                None,
                does_not_have("debug_dump", member_kind="method"),
            ]
        """)
    class_entity = next(entity for entity in entities if entity.kind == "class")

    entries = normalize_declaration_entries(class_entity)

    assert len(entries) == 1
    assert entries[0].kind == "does_not_have"
    assert entries[0].params == {
        "name": "debug_dump",
        "member_kind": "method",
    }


def test_multiple_does_not_have_declarations_get_unique_rule_ids() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import does_not_have

        class User:
            __archtest__: Annotated[
                None,
                does_not_have("debug_dump", member_kind="method"),
            ]
            __archtest__: Annotated[
                None,
                does_not_have("password", member_kind="attribute", storage="instance"),
            ]
        """)
    class_entity = next(entity for entity in entities if entity.kind == "class")

    rules, evidence, compiler_results = compile_rules([class_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == [
        "NEG001/does_not_have/v1/d0",
        "NEG001/does_not_have/v1/d1",
    ]


def test_flow_declarations_are_preserved_without_deduping_and_enforce_flow_compiles() -> (
    None
):
    entities = _extract_entities("""
        from typing import Annotated
        from pythonarchtesting.rules import enforce_flow, flow

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
        from pythonarchtesting.rules import enforce_flow, flow

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
