"""
Tests for entity extraction and determinism.
"""

import textwrap
from pathlib import Path

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.config.projects import TargetSpec
from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.entities_extraction import (
    extract_entities_from_source,
    extract_entities_from_source_with_nonmatchable,
)
from pythonarchtesting.run_state import RunState
from pythonarchtesting.runner import evaluate_target


def _empty_run_state(config) -> RunState:
    empty_index = build_entity_index([])
    return RunState(
        config=config,
        source_path=Path("."),
        reference_modules=[],
        source_entities=[],
        source_index=empty_index,
        source_by_id={},
        rules=[],
        compiler_results=[],
        compiler_validations=[],
        run_generated_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
        framework_version="test",
    )


def test_entity_extraction_deterministic(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text(textwrap.dedent("""
            def f():
                return 1
            """).strip() + "\n")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("CONST = 1\n")
    (pkg / "mod.py").write_text(textwrap.dedent("""
            def g(x, *, y=1):
                return x + y
            """).strip() + "\n")

    config = create_config_from_dict({})
    run_state = _empty_run_state(config)
    spec = TargetSpec(target_id="target", path=tmp_path)

    target_state_first = evaluate_target(run_state=run_state, spec=spec)
    ids_first = [e.canonical_id for e in target_state_first.target_entities]

    target_state_second = evaluate_target(run_state=run_state, spec=spec)
    ids_second = [e.canonical_id for e in target_state_second.target_entities]

    assert ids_first == ids_second
    assert all("\\" not in e.filepath_rel for e in target_state_first.target_entities)
    assert any(e.kind == "module" for e in target_state_first.target_entities)

    mod_entities = [
        e for e in target_state_first.target_entities if e.module_path == "pkg.mod"
    ]
    assert mod_entities


def test_nested_function_evidence(tmp_path: Path) -> None:
    (tmp_path / "nested.py").write_text(textwrap.dedent("""
            def outer():
                def inner():
                    return 1
                return inner()
            """).strip() + "\n")

    source = (tmp_path / "nested.py").read_text(encoding="utf-8")
    matchable, non_matchable = extract_entities_from_source_with_nonmatchable(
        source,
        tmp_path / "nested.py",
        tmp_path,
        None,
        role="target",
        include_nested_functions=False,
    )

    assert all(e.name != "inner" for e in matchable)
    assert any(e.name == "inner" for e in non_matchable)

    outer = next(e for e in matchable if e.name == "outer")
    meta = outer.surface_meta
    assert meta.get("nested") is True
    assert outer.decorators_meta is meta
    nested_functions = meta.get("nested_functions", [])
    assert any(item.get("name") == "inner" for item in nested_functions)


def test_surface_meta_aliases_decorators_meta() -> None:
    source = textwrap.dedent("""
            class Example:
                @staticmethod
                def run():
                    return 1
            """).strip() + "\n"

    entities = extract_entities_from_source(
        source,
        Path("module.py"),
        Path("."),
        None,
        role="target",
        include_nested_functions=False,
    )

    method = next(entity for entity in entities if entity.qualname == "Example.run")

    assert method.surface_meta is method.decorators_meta
    assert method.surface_meta["method_kind"] == "static"


def test_class_extraction_preserves_normalized_bases() -> None:
    source = textwrap.dedent("""
            from typing import Protocol as TypingProtocol

            class Repository(TypingProtocol):
                pass
            """).strip() + "\n"

    entities = extract_entities_from_source(
        source,
        Path("module.py"),
        Path("."),
        None,
        role="target",
        include_nested_functions=False,
    )

    repository = next(
        entity
        for entity in entities
        if entity.kind == "class" and entity.name == "Repository"
    )

    assert repository.extras["bases"] == ["typing.Protocol"]


def test_class_extraction_preserves_typing_extensions_protocol_base() -> None:
    source = textwrap.dedent("""
            from typing_extensions import Protocol as ExtProtocol

            class Repository(ExtProtocol):
                pass
            """).strip() + "\n"

    entities = extract_entities_from_source(
        source,
        Path("module.py"),
        Path("."),
        None,
        role="target",
        include_nested_functions=False,
    )

    repository = next(
        entity
        for entity in entities
        if entity.kind == "class" and entity.name == "Repository"
    )

    assert repository.extras["bases"] == ["typing_extensions.Protocol"]


def test_method_annotations_ignore_self_for_has_all() -> None:
    source = textwrap.dedent("""
            class Calculator:
                def add(self, a: int, b: int) -> int:
                    return a + b
            """).strip() + "\n"

    entities = extract_entities_from_source(
        source,
        Path("module.py"),
        Path("."),
        None,
        role="target",
        include_nested_functions=False,
    )

    add_entity = next(
        entity for entity in entities if entity.qualname == "Calculator.add"
    )
    annotations = add_entity.extras.get("annotations", {})

    assert annotations.get("has_all") is True
    args = annotations.get("args", [])
    assert args[0]["name"] == "self"
    assert args[0]["annotation"] is None
