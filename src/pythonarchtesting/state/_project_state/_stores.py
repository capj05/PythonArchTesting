from __future__ import annotations

from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

from pythonarchtesting.state.discovery import ModuleDiscovery
from pythonarchtesting.state.memory_manager import MemoryManager

FunctionLike = Any
FunctionRegistry = dict[str, list[FunctionLike]]
ValidationStats = dict[str, dict[Any, int]]
EvidenceCache = dict[str, list[Any]]


@dataclass
class ImportStore:
    imported_modules: dict[str, ModuleType] = field(default_factory=dict)
    target_functions: FunctionRegistry = field(default_factory=dict)
    import_order: list[str] = field(default_factory=list)
    import_stack: list[str] = field(default_factory=list)
    sys_path_inserted: str | None = None

    def reset(self) -> None:
        self.imported_modules = {}
        self.target_functions = {}
        self.import_order = []
        self.import_stack = []
        self.sys_path_inserted = None


@dataclass
class ValidationStore:
    validation_results: list[Any] = field(default_factory=list)
    validation_stats: ValidationStats = field(default_factory=dict)

    def reset(self) -> None:
        self.validation_results = []
        self.validation_stats = {}


@dataclass
class EntityStore:
    source_entities: list[Any] = field(default_factory=list)
    target_entities: list[Any] = field(default_factory=list)
    source_non_matchable_entities: list[Any] = field(default_factory=list)
    target_non_matchable_entities: list[Any] = field(default_factory=list)
    source_index: Any = None
    target_index: Any = None
    source_by_id: dict[str, Any] = field(default_factory=dict)
    target_by_id: dict[str, Any] = field(default_factory=dict)

    def reset(self) -> None:
        self.source_entities = []
        self.target_entities = []
        self.source_non_matchable_entities = []
        self.target_non_matchable_entities = []
        self.source_index = None
        self.target_index = None
        self.source_by_id = {}
        self.target_by_id = {}


@dataclass
class MatchStore:
    match_results: list[Any] = field(default_factory=list)
    match_by_source_id: dict[str, Any] = field(default_factory=dict)
    match_registry: dict[str, Any] = field(default_factory=dict)

    def reset(self) -> None:
        self.match_results = []
        self.match_by_source_id = {}
        self.match_registry = {}


@dataclass
class RuleStore:
    rules: list[Any] = field(default_factory=list)
    rule_results: list[Any] = field(default_factory=list)

    def reset(self) -> None:
        self.rules = []
        self.rule_results = []


@dataclass
class EvidenceStore:
    static_evidence_cache: EvidenceCache | None = None

    def reset(self) -> None:
        self.static_evidence_cache = None


@dataclass
class ProjectStores:
    imports: ImportStore = field(default_factory=ImportStore)
    validation: ValidationStore = field(default_factory=ValidationStore)
    entities: EntityStore = field(default_factory=EntityStore)
    matches: MatchStore = field(default_factory=MatchStore)
    rules: RuleStore = field(default_factory=RuleStore)
    evidence: EvidenceStore = field(default_factory=EvidenceStore)

    def reset_imports(self) -> None:
        self.imports.reset()

    def reset_validation(self) -> None:
        self.validation.reset()

    def reset_analysis(self) -> None:
        self.entities.reset()
        self.matches.reset()
        self.rules.reset()

    def reset_evidence(self) -> None:
        self.evidence.reset()


@dataclass
class ProjectServices:
    memory_manager: MemoryManager
    module_discovery: ModuleDiscovery
