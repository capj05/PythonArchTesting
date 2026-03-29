from __future__ import annotations

from pathlib import Path

from src.entities import Entity
from src.entities_extraction import extract_entities_from_source
from src.protocols.signature_inference import infer_signature_target_reference


def _extract_entities(source_text: str) -> list[Entity]:
    return extract_entities_from_source(
        source_text=source_text,
        file_path=Path("target_module.py"),
        root_path=Path("."),
        target_module_name=None,
        role="target",
        include_nested_functions=False,
        root_label="target",
    )


def _extract_entity(source_text: str, *, kind: str, name: str) -> Entity:
    for entity in _extract_entities(source_text):
        if entity.kind == kind and entity.name == name:
            return entity
    raise AssertionError(f"Entity '{name}' ({kind}) not found")


def test_infers_direct_constructor_return() -> None:
    target = """
class SqlService:
    pass

def build():
    return SqlService()
"""
    entities = _extract_entities(target)
    target_entity = _extract_entity(target, kind="function", name="build")

    result = infer_signature_target_reference(
        target_entity, subject_kind="return", subject_index=-1, entities=entities
    )

    assert result is not None
    assert result.reference == "SqlService"
    assert result.inference_kind == "return_direct_constructor"
    assert result.failure_reason is None


def test_infers_assigned_local_constructor_return() -> None:
    target = """
class SqlService:
    pass

def build():
    service = SqlService()
    return service
"""
    entities = _extract_entities(target)
    target_entity = _extract_entity(target, kind="function", name="build")

    result = infer_signature_target_reference(
        target_entity, subject_kind="return", subject_index=-1, entities=entities
    )

    assert result is not None
    assert result.reference == "SqlService"
    assert result.inference_kind == "return_assigned_local_constructor"
    assert result.failure_reason is None


def test_infers_parameter_default_constructor() -> None:
    target = """
class SqlRepository:
    pass

def process(repo=SqlRepository()) -> None:
    return None
"""
    entities = _extract_entities(target)
    target_entity = _extract_entity(target, kind="function", name="process")

    result = infer_signature_target_reference(
        target_entity, subject_kind="param", subject_index=0, entities=entities
    )

    assert result is not None
    assert result.reference == "SqlRepository"
    assert result.inference_kind == "param_default_constructor"
    assert result.failure_reason is None


def test_reports_conflicting_local_constructors() -> None:
    target = """
class SqlService:
    pass

class AltService:
    pass

def build(flag: bool):
    if flag:
        return SqlService()
    return AltService()
"""
    entities = _extract_entities(target)
    target_entity = _extract_entity(target, kind="function", name="build")

    result = infer_signature_target_reference(
        target_entity, subject_kind="return", subject_index=-1, entities=entities
    )

    assert result is not None
    assert result.reference is None
    assert result.inference_kind == "return_conflicting_local_constructors"
    assert result.failure_reason == "ambiguous_or_missing"


def test_follows_one_hop_same_module_helper() -> None:
    target = """
class SqlService:
    pass

def make_service():
    return SqlService()

def build():
    return make_service()
"""
    entities = _extract_entities(target)
    target_entity = _extract_entity(target, kind="function", name="build")

    result = infer_signature_target_reference(
        target_entity, subject_kind="return", subject_index=-1, entities=entities
    )

    assert result is not None
    assert result.reference == "SqlService"
    assert result.inference_kind == "return_same_module_helper_constructor"
    assert result.failure_reason is None


def test_propagates_helper_conflicts() -> None:
    target = """
class SqlService:
    pass

class AltService:
    pass

def make_service(flag: bool):
    if flag:
        return SqlService()
    return AltService()

def build():
    return make_service(True)
"""
    entities = _extract_entities(target)
    target_entity = _extract_entity(target, kind="function", name="build")

    result = infer_signature_target_reference(
        target_entity, subject_kind="return", subject_index=-1, entities=entities
    )

    assert result is not None
    assert result.reference is None
    assert result.inference_kind == "return_conflicting_local_constructors"
    assert result.failure_reason == "ambiguous_or_missing"


def test_does_not_follow_nested_helper_chain() -> None:
    target = """
class SqlService:
    pass

def inner_service():
    return SqlService()

def make_service():
    return inner_service()

def build():
    return make_service()
"""
    entities = _extract_entities(target)
    target_entity = _extract_entity(target, kind="function", name="build")

    result = infer_signature_target_reference(
        target_entity, subject_kind="return", subject_index=-1, entities=entities
    )

    assert result is None


def test_detects_same_module_helper_cycle() -> None:
    target = """
def build():
    return make_service()

def make_service():
    return build()
"""
    entities = _extract_entities(target)
    target_entity = _extract_entity(target, kind="function", name="build")

    result = infer_signature_target_reference(
        target_entity, subject_kind="return", subject_index=-1, entities=entities
    )

    assert result is not None
    assert result.reference is None
    assert result.inference_kind == "return_same_module_helper_cycle"
    assert result.failure_reason == "ambiguous_or_missing"
