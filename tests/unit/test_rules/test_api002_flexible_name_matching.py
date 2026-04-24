from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

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


def _find_entity(
    entities: list[Entity],
    *,
    kind: str,
    name: str,
) -> Entity:
    for entity in entities:
        if entity.kind == kind and entity.name == name:
            return entity
    raise AssertionError(f"Entity '{name}' ({kind}) not found")


def _compile(source_text: str) -> tuple[list[object], list[object], list[object]]:
    source_entities = _extract_entities(source_text, role="source")
    return compile_rules(source_entities, Mock())


def _evaluate(
    source_text: str,
    target_text: str,
    *,
    method_match_status: MatchStatus = MatchStatus.LOW_CONFIDENCE,
    method_target_name: str | None = None,
    class_name: str = "Processor",
    method_name: str = "run",
) -> tuple[object, list[object]]:
    source_entities = _extract_entities(source_text, role="source")
    target_entities = _extract_entities(target_text, role="target")
    source_method = _find_entity(source_entities, kind="method", name=method_name)
    source_class = _find_entity(source_entities, kind="class", name=class_name)
    target_class = _find_entity(target_entities, kind="class", name=class_name)
    target_method = (
        _find_entity(target_entities, kind="method", name=method_target_name)
        if method_target_name is not None
        else None
    )

    rules, _, _ = compile_rules(source_entities, Mock())
    matches = {
        source_method.canonical_id: MatchResult(
            source_id=source_method.canonical_id,
            status=method_match_status,
            target_id=target_method.canonical_id if target_method else None,
            confidence=1.0 if method_target_name is not None else 0.2,
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

    assert len(results) == 1
    return results[0], errors


def test_api002_compile_threads_alias_name_matching_params() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[
            None,
            required_method(name_match="alias", aliases=["execute"]),
        ]
        return data
"""
    rules, evidence, compiler_results = _compile(source)

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API002/required_method/v1"]
    assert rules[0].params["name_match"] == "alias"
    assert rules[0].params["aliases"] == ["execute"]
    assert rules[0].params["pattern"] is None


def test_api002_compile_threads_regex_name_matching_params() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[
            None,
            required_method(name_match="regex", pattern="fetch_[a-z]+"),
        ]
        return data
"""
    rules, evidence, compiler_results = _compile(source)

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API002/required_method/v1"]
    assert rules[0].params["name_match"] == "regex"
    assert rules[0].params["aliases"] is None
    assert rules[0].params["pattern"] == "fetch_[a-z]+"


def test_api002_compile_threads_any_name_matching_params() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[
            None,
            required_method(name_match="any"),
        ]
        return data
"""
    rules, evidence, compiler_results = _compile(source)

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API002/required_method/v1"]
    assert rules[0].params["name_match"] == "any"
    assert rules[0].params["aliases"] is None
    assert rules[0].params["pattern"] is None


@pytest.mark.parametrize(
    ("declaration", "reason_fragment"),
    [
        (
            'required_method(name_match="exact", aliases=["execute"])',
            "exact name matching does not accept aliases or pattern",
        ),
        (
            'required_method(name_match="regex", aliases=["execute"], pattern="run")',
            "regex name matching does not accept aliases",
        ),
        (
            'required_method(name_match="regex", pattern="[")',
            "invalid regex pattern",
        ),
        (
            'required_method(name_match="any", pattern="run")',
            "any name matching does not accept aliases or pattern",
        ),
    ],
)
def test_api002_compile_rejects_invalid_flexible_name_matching_combinations(
    declaration: str,
    reason_fragment: str,
) -> None:
    source = f"""
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, {declaration}]
        return data
"""
    rules, evidence, compiler_results = _compile(source)

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]
    assert reason_fragment in evidence[0].payload["reason"]


def test_api002_alias_name_matching_passes_via_class_fallback() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[
            None,
            required_method(name_match="alias", aliases=["execute"]),
        ]
        return data
"""
    target = """
class Processor:
    def execute(self, data: int) -> int:
        return data
"""
    result, errors = _evaluate(source, target)

    assert errors == []
    assert result.status == "OK"
    assert result.details["name_match"] == "alias"
    assert result.details["resolved_candidate"] == "execute"
    assert result.details["member_origin"] == "declared"


def test_api002_alias_name_matching_fails_for_incompatible_signature() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[
            None,
            required_method(name_match="alias", aliases=["execute"]),
        ]
        return data
"""
    target = """
class Processor:
    def execute(self, data: str) -> int:
        return 1
"""
    result, errors = _evaluate(source, target)

    assert errors == []
    assert result.status == "FAILED"
    assert result.details["failure_reason"] == "no_compatible_candidate_for_aliases"
    assert result.details["candidate_names"] == ["execute"]


def test_api002_regex_name_matching_passes_for_single_compatible_candidate() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[
            None,
            required_method(name_match="regex", pattern="fetch_[a-z]+"),
        ]
        return data
"""
    target = """
class Processor:
    def helper(self, data: int) -> int:
        return data

    def fetch_data(self, data: int) -> int:
        return data
"""
    result, errors = _evaluate(source, target)

    assert errors == []
    assert result.status == "OK"
    assert result.details["resolved_candidate"] == "fetch_data"
    assert result.details["resolution_mode"] == "regex"


def test_api002_regex_name_matching_fails_for_ambiguous_candidates() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[
            None,
            required_method(name_match="regex", pattern="fetch_[a-z]+"),
        ]
        return data
"""
    target = """
class Processor:
    def fetch_data(self, data: int) -> int:
        return data

    def fetch_value(self, data: int) -> int:
        return data
"""
    result, errors = _evaluate(source, target)

    assert errors == []
    assert result.status == "FAILED"
    assert result.details["failure_reason"] == "multiple_compatible_candidates"
    assert sorted(result.details["ambiguity"]["compatible_candidates"]) == [
        "fetch_data",
        "fetch_value",
    ]


def test_api002_any_name_matching_passes_for_single_compatible_candidate() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method(name_match="any")]
        return data
"""
    target = """
class Processor:
    def process(self, data: int) -> int:
        return data
"""
    result, errors = _evaluate(source, target)

    assert errors == []
    assert result.status == "OK"
    assert result.details["resolved_candidate"] == "process"
    assert result.details["resolution_mode"] == "any"


def test_api002_any_name_matching_fails_when_no_compatible_candidate_exists() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method(name_match="any")]
        return data
"""
    target = """
class Processor:
    def process(self, data: str) -> int:
        return 1
"""
    result, errors = _evaluate(source, target)

    assert errors == []
    assert result.status == "FAILED"
    assert result.details["failure_reason"] == "no_compatible_candidate_for_any_name"


def test_api002_any_name_matching_fails_for_ambiguous_candidates() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method(name_match="any")]
        return data
"""
    target = """
class Processor:
    def load(self, data: int) -> int:
        return data

    def fetch(self, data: int) -> int:
        return data
"""
    result, errors = _evaluate(source, target)

    assert errors == []
    assert result.status == "FAILED"
    assert result.details["failure_reason"] == "multiple_compatible_candidates"
    assert sorted(result.details["ambiguity"]["compatible_candidates"]) == [
        "fetch",
        "load",
    ]


def test_api002_alias_name_matching_supports_inherited_methods() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[
            None,
            required_method(name_match="alias", aliases=["execute"]),
        ]
        return data
"""
    target = """
class BaseProcessor:
    def execute(self, data: int) -> int:
        return data


class Processor(BaseProcessor):
    pass
"""
    result, errors = _evaluate(source, target)

    assert errors == []
    assert result.status == "OK"
    assert result.details["member_origin"] == "inherited"
    assert result.details["resolved_candidate"] == "execute"
