from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.core.evaluation import evaluate_rules_for_target
from pythonarchtesting.entities import Entity, build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import MatchResult, MatchStatus
from pythonarchtesting.rules.compilation import compile_rules


def _extract_entities(source_text: str, *, role: str) -> list[Entity]:
    return extract_entities_from_source(
        source_text=source_text,
        file_path=Path(f"{role}_module.py"),
        root_path=Path("."),
        target_module_name=None,
        role=role,  # type: ignore[arg-type]
        include_nested_functions=False,
        root_label=role,
    )


def _extract_entity(
    source_text: str,
    *,
    role: str,
    kind: str,
    name: str,
) -> Entity:
    entities = extract_entities_from_source(
        source_text=source_text,
        file_path=Path(f"{role}_module.py"),
        root_path=Path("."),
        target_module_name=None,
        role=role,  # type: ignore[arg-type]
        include_nested_functions=False,
        root_label=role,
    )
    for entity in entities:
        if entity.kind == kind and entity.name == name:
            return entity
    raise AssertionError(f"Entity '{name}' ({kind}) not found for role={role}")


def test_api002_compile_emits_required_method_rule():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method()]
        return data
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API002/required_method/v1"]
    assert [rule.rule_type for rule in rules] == ["api_signature"]
    assert rules[0].params["declared_only"] is False
    assert rules[0].params["enforce_method_kind"] is True
    assert rules[0].params["allow_missing"] is False
    assert rules[0].params["fail_on_unmatched"] is True
    assert rules[0].params["name_match"] == "exact"
    assert rules[0].params["aliases"] is None
    assert rules[0].params["pattern"] is None


def test_api002_compile_emits_required_method_rule_from_annotation() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method(signature_mode="compatible")]
        return data
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API002/required_method/v1"]
    assert [rule.rule_type for rule in rules] == ["api_signature"]
    assert rules[0].params["declared_only"] is False
    assert rules[0].params["enforce_method_kind"] is True
    assert rules[0].params["allow_missing"] is False
    assert rules[0].params["fail_on_unmatched"] is True


def test_api002_compile_accepts_any_signature_mode() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method(signature_mode="any")]
        return data
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API002/required_method/v1"]
    assert rules[0].params["mode"] == "any"


def test_api002_compile_unknown_signature_mode_defaults_to_compatible() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method(signature_mode="nope")]
        return data
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API002/required_method/v1"]
    assert rules[0].params["mode"] == "compatible"


def test_api002_compile_threads_allow_missing_flag() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[
            None,
            required_method(signature_mode="compatible", allow_missing=True),
        ]
        return data
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API002/required_method/v1"]
    assert rules[0].params["allow_missing"] is True
    assert rules[0].params["fail_on_unmatched"] is False


def test_api002_compile_threads_declared_only_flag() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[
            None,
            required_method(signature_mode="compatible", declared_only=True),
        ]
        return data
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API002/required_method/v1"]
    assert rules[0].params["declared_only"] is True


def test_api002_evaluation_passes_for_compatible_method():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    @classmethod
    def from_path(cls, path: str) -> "Processor":
        __archtest__: Annotated[
            None,
            required_method(signature_mode="compatible"),
        ]
        return cls()
"""
    target = """
class Processor:
    @classmethod
    def from_path(cls, path: str) -> "Processor":
        return cls()
"""
    source_entity = _extract_entity(
        source, role="source", kind="method", name="from_path"
    )
    target_entity = _extract_entity(
        target, role="target", kind="method", name="from_path"
    )

    rules, _, _ = compile_rules([source_entity], Mock())
    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([target_entity])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api002_evaluation_fails_for_method_kind_mismatch():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    @classmethod
    def from_path(cls, path: str) -> "Processor":
        __archtest__: Annotated[None, required_method()]
        return cls()
"""
    target = """
class Processor:
    def from_path(self, path: str) -> "Processor":
        return self
"""
    source_entity = _extract_entity(
        source, role="source", kind="method", name="from_path"
    )
    target_entity = _extract_entity(
        target, role="target", kind="method", name="from_path"
    )

    rules, _, _ = compile_rules([source_entity], Mock())
    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([target_entity])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "method kind mismatch" in results[0].message


def test_api002_any_mode_ignores_parameter_shape() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int, retries: int = 3) -> int:
        __archtest__: Annotated[None, required_method(signature_mode="any")]
        return data
"""
    target = """
class Processor:
    def run(self, payload: str, enabled: bool, *, timeout: float) -> int:
        return 1
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    target_entity = _extract_entity(target, role="target", kind="method", name="run")

    rules, _, _ = compile_rules([source_entity], Mock())
    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([target_entity])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["mode"] == "any"
    assert results[0].details["params_ignored"] is True


def test_api002_any_mode_ignores_varargs_and_kwargs() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, *args: int, **kwargs: str) -> int:
        __archtest__: Annotated[None, required_method(signature_mode="any")]
        return 1
"""
    target = """
class Processor:
    def run(self, value: int) -> int:
        return value
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    target_entity = _extract_entity(target, role="target", kind="method", name="run")

    rules, _, _ = compile_rules([source_entity], Mock())
    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([target_entity])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["params_ignored"] is True


def test_api002_any_mode_still_fails_for_async_sync_mismatch() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    async def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method(signature_mode="any")]
        return data
"""
    target = """
class Processor:
    def run(self, payload: str, enabled: bool) -> int:
        return 1
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    target_entity = _extract_entity(target, role="target", kind="method", name="run")

    rules, _, _ = compile_rules([source_entity], Mock())
    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([target_entity])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "async/sync mismatch for required method" in results[0].message
    assert results[0].details["params_ignored"] is True


def test_api002_any_mode_still_fails_for_method_kind_mismatch() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    @classmethod
    def run(cls, data: int) -> int:
        __archtest__: Annotated[None, required_method(signature_mode="any")]
        return data
"""
    target = """
class Processor:
    def run(self, payload: str, enabled: bool) -> int:
        return 1
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    target_entity = _extract_entity(target, role="target", kind="method", name="run")

    rules, _, _ = compile_rules([source_entity], Mock())
    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([target_entity])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "method kind mismatch" in results[0].message
    assert results[0].details["params_ignored"] is True


def test_api002_any_mode_allows_method_kind_mismatch_when_disabled() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    @classmethod
    def run(cls, data: int) -> int:
        __archtest__: Annotated[
            None,
            required_method(
                signature_mode="any",
                enforce_method_kind=False,
            ),
        ]
        return data
"""
    target = """
class Processor:
    def run(self, payload: str, enabled: bool) -> int:
        return 1
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    target_entity = _extract_entity(target, role="target", kind="method", name="run")

    rules, _, _ = compile_rules([source_entity], Mock())
    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([target_entity])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["params_ignored"] is True


def test_api002_unmatched_required_method_fails():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method()]
        return data
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    rules, _, _ = compile_rules([source_entity], Mock())

    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.UNMATCHED,
            target_id=None,
            confidence=0.2,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "Required target entity missing or not matchable" in results[0].message


def test_api002_unmatched_optional_method_skips() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method(allow_missing=True)]
        return data
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    rules, _, _ = compile_rules([source_entity], Mock())

    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.UNMATCHED,
            target_id=None,
            confidence=0.2,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["SKIPPED"]
    assert results[0].details["reason"] == "match_status"
    assert results[0].details["match_status"] == "unmatched"


def test_api002_optional_method_present_but_incompatible_still_fails() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method(allow_missing=True)]
        return data
"""
    target = """
class Processor:
    def run(self, data: str) -> int:
        return 0
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    target_entity = _extract_entity(target, role="target", kind="method", name="run")

    rules, _, _ = compile_rules([source_entity], Mock())
    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([target_entity])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["allow_missing"] is True
    assert any(
        "parameter annotation mismatch" in error
        for error in results[0].details["errors"]
    )


def test_api002_compile_non_method_emits_compiler_evidence():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

def run(data: int) -> int:
    __archtest__: Annotated[None, required_method()]
    return data
"""
    source_entity = _extract_entity(source, role="source", kind="function", name="run")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


def test_api002_inherited_method_satisfies_requirement_by_default() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method()]
        return data
"""
    target = """
class BaseProcessor:
    def run(self, data: int) -> int:
        return data


class Processor(BaseProcessor):
    pass
"""
    source_entities = _extract_entities(source, role="source")
    target_entities = _extract_entities(target, role="target")
    source_method = next(
        entity
        for entity in source_entities
        if entity.kind == "method" and entity.name == "run"
    )
    source_class = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Processor"
    )
    target_class = next(
        entity
        for entity in target_entities
        if entity.kind == "class" and entity.name == "Processor"
    )

    rules, _, _ = compile_rules(source_entities, Mock())
    matches = {
        source_method.canonical_id: MatchResult(
            source_id=source_method.canonical_id,
            status=MatchStatus.UNMATCHED,
            target_id=None,
            confidence=0.2,
            reasons=[],
            candidates=[],
        ),
        source_class.canonical_id: MatchResult(
            source_id=source_class.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_class.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["declared_only"] is False
    assert results[0].details["member_origin"] == "inherited"


def test_api002_declared_only_rejects_inherited_method() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method(declared_only=True)]
        return data
"""
    target = """
class BaseProcessor:
    def run(self, data: int) -> int:
        return data


class Processor(BaseProcessor):
    pass
"""
    source_entities = _extract_entities(source, role="source")
    target_entities = _extract_entities(target, role="target")
    source_method = next(
        entity
        for entity in source_entities
        if entity.kind == "method" and entity.name == "run"
    )
    source_class = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Processor"
    )
    target_class = next(
        entity
        for entity in target_entities
        if entity.kind == "class" and entity.name == "Processor"
    )

    rules, _, _ = compile_rules(source_entities, Mock())
    matches = {
        source_method.canonical_id: MatchResult(
            source_id=source_method.canonical_id,
            status=MatchStatus.UNMATCHED,
            target_id=None,
            confidence=0.2,
            reasons=[],
            candidates=[],
        ),
        source_class.canonical_id: MatchResult(
            source_id=source_class.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_class.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "inherited but not declared directly on target class" in results[0].message
    assert results[0].details["declared_only"] is True
    assert results[0].details["member_origin"] == "inherited"


def test_api002_optional_missing_method_skips_via_class_fallback() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method(allow_missing=True)]
        return data
"""
    target = """
class Processor:
    pass
"""
    source_entities = _extract_entities(source, role="source")
    target_entities = _extract_entities(target, role="target")
    source_method = next(
        entity
        for entity in source_entities
        if entity.kind == "method" and entity.name == "run"
    )
    source_class = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Processor"
    )
    target_class = next(
        entity
        for entity in target_entities
        if entity.kind == "class" and entity.name == "Processor"
    )

    rules, _, _ = compile_rules(source_entities, Mock())
    matches = {
        source_method.canonical_id: MatchResult(
            source_id=source_method.canonical_id,
            status=MatchStatus.UNMATCHED,
            target_id=None,
            confidence=0.2,
            reasons=[],
            candidates=[],
        ),
        source_class.canonical_id: MatchResult(
            source_id=source_class.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_class.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["SKIPPED"]
    assert results[0].details["allow_missing"] is True
    assert results[0].details["reason"] == "optional_member_absent"
    assert results[0].details["member_origin"] == "missing"
