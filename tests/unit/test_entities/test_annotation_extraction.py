import textwrap
from pathlib import Path

from src.entities_extraction import extract_entities_from_source


def _extract_entities(source: str):
    return extract_entities_from_source(
        textwrap.dedent(source).strip() + "\n",
        Path("sample.py"),
        Path("."),
        None,
        role="source",
        include_nested_functions=False,
    )


def test_annotation_marker_extraction_across_supported_scopes() -> None:
    entities = _extract_entities("""
        import typing
        from typing import Annotated
        from src.rules import (
            forbid_imports,
            implements_protocol,
            required_entity_signature,
            required_method,
        )

        __archtest__: Annotated[None, forbid_imports("statistics", scope="package")]

        class Service:
            __archtest__: Annotated[None, required_method, implements_protocol("sample.Repository")]

            def run(self, value: int) -> int:
                __archtest__: typing.Annotated[
                    None,
                    required_method(signature_mode="exact"),
                    required_entity_signature(mode="compatible"),
                ]
                return value
        """)

    module_entity = next(entity for entity in entities if entity.kind == "module")
    class_entity = next(entity for entity in entities if entity.kind == "class")
    method_entity = next(entity for entity in entities if entity.kind == "method")

    assert [decl.kind for decl in module_entity.annotation_declarations] == [
        "forbid_imports"
    ]
    assert module_entity.annotation_declarations[0].params == {
        "forbidden": ["statistics"],
        "scope": "package",
    }

    assert [decl.kind for decl in class_entity.annotation_declarations] == [
        "required_method",
        "implements_protocol",
    ]
    assert class_entity.annotation_declarations[0].raw == "required_method"
    assert class_entity.annotation_declarations[1].params == {
        "protocol": "sample.Repository",
        "protocol_expr": "'sample.Repository'",
    }

    assert [decl.kind for decl in method_entity.annotation_declarations] == [
        "required_method",
        "required_entity_signature",
    ]
    assert [decl.order for decl in method_entity.annotation_declarations] == [0, 1]
    assert method_entity.annotation_declarations[0].params == {
        "signature_mode": "exact"
    }
    assert method_entity.annotation_declarations[1].params == {"mode": "compatible"}
    assert all(
        decl.base_annotation == "None" for decl in method_entity.annotation_declarations
    )


def test_annotation_markers_preserve_source_order_across_multiple_statements() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import (
            forbid_imports,
            required_entity_signature,
            required_method,
        )

        def process(value: int) -> int:
            __archtest__: Annotated[None, required_entity_signature]
            __archtest__: Annotated[
                None,
                required_method(signature_mode="exact"),
                forbid_imports("statistics", scope="entity"),
            ]
            return value
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")

    assert [decl.kind for decl in function_entity.annotation_declarations] == [
        "required_entity_signature",
        "required_method",
        "forbid_imports",
    ]
    assert [decl.order for decl in function_entity.annotation_declarations] == [0, 1, 2]
    assert function_entity.annotation_declarations[1].params == {
        "signature_mode": "exact"
    }


def test_annotation_marker_records_unsupported_cases_without_failing_extraction() -> (
    None
):
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import required_method

        __archtest__: Annotated[None, required_method(signature_mode="exact")] = None

        def process() -> None:
            __archtest__: list[int]
            __archtest__: Annotated[None, "custom"]
            if True:
                __archtest__: Annotated[None, required_method(signature_mode="exact")]
            return None
        """)

    module_entity = next(entity for entity in entities if entity.kind == "module")
    function_entity = next(entity for entity in entities if entity.kind == "function")

    assert module_entity.annotation_declarations[0].kind == "required_method"
    assert {
        issue["kind"] for issue in module_entity.annotation_declarations[0].unsupported
    } == {"assigned_value"}

    assert [decl.kind for decl in function_entity.annotation_declarations] == [
        "unknown",
        "unknown",
        "required_method",
    ]
    assert (
        function_entity.annotation_declarations[0].unsupported[0]["kind"] == "container"
    )
    assert (
        function_entity.annotation_declarations[1].unsupported[0]["kind"] == "metadata"
    )
    assert (
        function_entity.annotation_declarations[2].unsupported[0]["kind"] == "surface"
    )
    assert all(
        issue["kind"] != "assigned_value"
        for decl in function_entity.annotation_declarations
        for issue in decl.unsupported
    )


def test_signature_annotation_markers_extract_supported_param_and_return_metadata() -> (
    None
):
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import required_entity_signature

        def normalize(
            value: Annotated[str, required_entity_signature(mode="compatible")],
        ) -> Annotated[str, required_entity_signature(mode="exact")]:
            return value.strip()
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")

    assert [decl.kind for decl in function_entity.annotation_declarations] == [
        "required_entity_signature",
        "required_entity_signature",
    ]
    assert [decl.order for decl in function_entity.annotation_declarations] == [0, 1]
    assert function_entity.annotation_declarations[0].params == {"mode": "compatible"}
    assert function_entity.annotation_declarations[1].params == {"mode": "exact"}
    assert [
        (
            decl.surface,
            decl.subject_kind,
            decl.subject_index,
            decl.subject_name,
        )
        for decl in function_entity.annotation_declarations
    ] == [
        ("signature", "param", 0, "value"),
        ("signature", "return", -1, "return"),
    ]
    assert [
        decl.base_annotation for decl in function_entity.annotation_declarations
    ] == [
        "str",
        "str",
    ]
    assert function_entity.extras["annotations"] == {
        "args": [{"name": "value", "annotation": "str"}],
        "return": "str",
        "has_all": True,
    }


def test_signature_annotation_markers_unwrap_qualified_annotated_base_text() -> None:
    entities = _extract_entities("""
        import typing
        from src.rules import required_entity_signature

        def normalize(
            value: typing.Annotated[
                str,
                required_entity_signature(mode="compatible"),
            ],
        ) -> typing.Annotated[str, required_entity_signature(mode="exact")]:
            return value.strip()
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")

    assert [
        decl.base_annotation for decl in function_entity.annotation_declarations
    ] == [
        "str",
        "str",
    ]
    assert function_entity.extras["annotations"] == {
        "args": [{"name": "value", "annotation": "str"}],
        "return": "str",
        "has_all": True,
    }


def test_signature_protocol_markers_extract_symbol_style_param_and_return_metadata() -> (
    None
):
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import implements_protocol

        class Repository:
            def get(self, item_id: str) -> str:
                ...

        def normalize(
            repo: Annotated[object, implements_protocol(Repository)],
        ) -> Annotated[object, implements_protocol(Repository)]:
            return repo
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")

    assert [decl.kind for decl in function_entity.annotation_declarations] == [
        "implements_protocol",
        "implements_protocol",
    ]
    assert [
        decl.params["protocol_expr"] for decl in function_entity.annotation_declarations
    ] == [
        "Repository",
        "Repository",
    ]
    assert [
        (decl.subject_kind, decl.subject_index, decl.subject_name)
        for decl in function_entity.annotation_declarations
    ] == [
        ("param", 0, "repo"),
        ("return", -1, "return"),
    ]


def test_annotation_marker_extracts_literal_tuple_metadata() -> None:
    entities = _extract_entities("""
        from typing import Annotated

        __archtest__: Annotated[
            None,
            ("forbid_imports", {"forbidden": ["statistics"], "scope": "package"}),
        ]

        def normalize(
            value: Annotated[str, ("required_entity_signature", {"mode": "compatible"})],
        ) -> Annotated[str, ("required_entity_signature", {"mode": "exact"})]:
            return value.strip()
        """)

    module_entity = next(entity for entity in entities if entity.kind == "module")
    function_entity = next(entity for entity in entities if entity.kind == "function")

    assert [decl.kind for decl in module_entity.annotation_declarations] == [
        "forbid_imports"
    ]
    assert module_entity.annotation_declarations[0].params == {
        "forbidden": ["statistics"],
        "scope": "package",
    }
    assert [decl.kind for decl in function_entity.annotation_declarations] == [
        "required_entity_signature",
        "required_entity_signature",
    ]
    assert [decl.params for decl in function_entity.annotation_declarations] == [
        {"mode": "compatible"},
        {"mode": "exact"},
    ]


def test_annotation_marker_records_invalid_literal_tuple_metadata_without_failing() -> (
    None
):
    entities = _extract_entities("""
        from typing import Annotated

        def normalize(
            value: Annotated[
                str,
                ("required_entity_signature", {"mode": "compatible"}, {"extra": False}),
                (123, {"mode": "compatible"}),
                ("required_entity_signature", ["compatible"]),
                ("custom_rule", {"enabled": True}),
                ("forbid_imports", {"forbidden": ["statistics"], "scope": "entity"}),
            ],
        ) -> str:
            return value.strip()
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")

    assert [decl.kind for decl in function_entity.annotation_declarations] == [
        "unknown",
        "unknown",
        "required_entity_signature",
        "custom_rule",
        "forbid_imports",
    ]
    assert (
        function_entity.annotation_declarations[0].unsupported[0]["kind"] == "metadata"
    )
    assert (
        function_entity.annotation_declarations[1].unsupported[0]["kind"] == "metadata"
    )
    assert (
        function_entity.annotation_declarations[2].unsupported[0]["kind"] == "metadata"
    )
    assert (
        function_entity.annotation_declarations[3].unsupported[0]["kind"]
        == "unknown_metadata"
    )
    assert (
        function_entity.annotation_declarations[4].unsupported[0]["kind"] == "surface"
    )


def test_signature_annotation_markers_follow_deterministic_scan_order() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import required_entity_signature

        def normalize(
            first: Annotated[int, required_entity_signature(mode="exact")],
            /,
            value: int,
            *args: Annotated[str, required_entity_signature(mode="compatible")],
            flag: Annotated[bool, required_entity_signature(return_annotation="off")],
            **kwargs: Annotated[dict[str, int], required_entity_signature(mode="loose")],
        ) -> Annotated[int, required_entity_signature(mode="strict")]:
            return value
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")

    assert [decl.kind for decl in function_entity.annotation_declarations] == [
        "required_entity_signature",
        "required_entity_signature",
        "required_entity_signature",
        "required_entity_signature",
        "required_entity_signature",
    ]
    assert [decl.order for decl in function_entity.annotation_declarations] == [
        0,
        1,
        2,
        3,
        4,
    ]
    assert [decl.params for decl in function_entity.annotation_declarations] == [
        {"mode": "exact"},
        {"mode": "compatible"},
        {"return_annotation": "off"},
        {"mode": "loose"},
        {"mode": "strict"},
    ]


def test_signature_annotation_markers_allow_protocol_markers() -> None:
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import forbid_imports, implements_protocol

        def normalize(
            value: Annotated[
                str,
                forbid_imports("statistics", scope="entity"),
                implements_protocol("sample.Repository"),
            ],
        ) -> str:
            return value
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")

    assert [decl.kind for decl in function_entity.annotation_declarations] == [
        "forbid_imports",
        "implements_protocol",
    ]
    assert (
        function_entity.annotation_declarations[0].unsupported[0]["kind"] == "surface"
    )
    assert function_entity.annotation_declarations[1].unsupported == []
    assert function_entity.annotation_declarations[1].surface == "signature"
    assert function_entity.annotation_declarations[1].subject_kind == "param"
    assert function_entity.annotation_declarations[1].subject_index == 0
    assert function_entity.annotation_declarations[1].subject_name == "value"
    assert function_entity.annotation_declarations[1].params == {
        "protocol_expr": "'sample.Repository'",
        "protocol": "sample.Repository",
    }


def test_body_markers_do_not_override_signature_declarations_of_same_rule_kind() -> (
    None
):
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import required_entity_signature, required_method

        def normalize(
            value: Annotated[str, required_entity_signature(mode="compatible")],
        ) -> Annotated[str, required_entity_signature(mode="compatible")]:
            __archtest__: Annotated[
                None,
                required_entity_signature(mode="exact"),
                required_method(signature_mode="exact"),
            ]
            return value.strip()
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")

    assert [decl.kind for decl in function_entity.annotation_declarations] == [
        "required_entity_signature",
        "required_entity_signature",
        "required_entity_signature",
        "required_method",
    ]
    assert [
        (decl.surface, decl.params) for decl in function_entity.annotation_declarations
    ] == [
        ("signature", {"mode": "compatible"}),
        ("signature", {"mode": "compatible"}),
        ("body", {"mode": "exact"}),
        ("body", {"signature_mode": "exact"}),
    ]


def test_function_body_flow_markers_extract_statement_surface_and_anchor_metadata() -> (
    None
):
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import enforce_flow, flow

        def normalize(value: str) -> str:
            current = value.strip()
            __archtest__: Annotated[None, flow("validated")]
            __archtest__: Annotated[None, enforce_flow(["validated"])]
            return current
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")

    assert [decl.kind for decl in function_entity.annotation_declarations] == [
        "flow",
        "enforce_flow",
    ]
    assert function_entity.annotation_declarations[0].surface == "statement"
    assert function_entity.annotation_declarations[0].params["stage"] == "validated"
    assert function_entity.annotation_declarations[0].params["variable"] == "current"
    assert function_entity.annotation_declarations[0].params["anchor_kind"] == "Assign"
    assert function_entity.annotation_declarations[1].surface == "body"


def test_nested_flow_markers_extract_while_nested_non_flow_markers_stay_invalid() -> (
    None
):
    entities = _extract_entities("""
        from typing import Annotated
        from src.rules import flow, required_method

        def normalize(value: str) -> str:
            current = value
            __archtest__: Annotated[None, flow("raw")]
            if value:
                current = value.strip()
                __archtest__: Annotated[None, flow("validated")]
                __archtest__: Annotated[None, required_method(signature_mode="exact")]
            return current
        """)

    function_entity = next(entity for entity in entities if entity.kind == "function")

    assert [decl.kind for decl in function_entity.annotation_declarations] == [
        "flow",
        "flow",
        "required_method",
    ]
    assert [decl.surface for decl in function_entity.annotation_declarations] == [
        "statement",
        "statement",
        "body",
    ]
    assert (
        function_entity.annotation_declarations[2].unsupported[0]["kind"] == "surface"
    )
