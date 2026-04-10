"""Canonical runtime state containers for source-once, target-per-run execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Rule, RuleResult
from pythonarchtesting.entities import Entity, EntityIndex
from pythonarchtesting.matching import MatchResult
from pythonarchtesting.state import ValidationResult


@dataclass(frozen=True)
class RunState:
    config: Config
    source_path: Path
    reference_modules: List[str]
    source_entities: List[Entity]
    source_index: EntityIndex
    source_by_id: Dict[str, Entity]
    rules: List[Rule]
    compiler_results: List[RuleResult]
    compiler_validations: List[ValidationResult]
    run_generated_at: datetime
    framework_version: str
    validation_scope: str = "all"


@dataclass
class TargetRunState:
    target_id: str
    target_path: Path
    target_entities: List[Entity]
    target_index: EntityIndex
    target_by_id: Dict[str, Entity]
    match_results: List[MatchResult]
    match_by_source: Dict[str, MatchResult]
    rule_results: List[RuleResult]
    validation_results: List[ValidationResult]
    exit_code: int = 0
