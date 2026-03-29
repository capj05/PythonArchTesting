from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.models import EvalContext, Evidence, Rule, RuleResult

from src.state.validation import (
    compiler_evidence_to_validation,
    rule_result_to_validation,
)

if TYPE_CHECKING:  # pragma: no cover
    from ._typing import ProjectStateLike


class ProjectStateRulesMixin:
    """Rule compilation + evaluation + wiring to ValidationResult."""

    def compile_rules(self: "ProjectStateLike") -> None:
        cfg = self._active_config()
        entity_rules: list[Rule] = []
        compiler_evidence: list[Evidence] = []
        compiler_results: list[RuleResult] = []

        if self.source_entities and self.source_index:
            from src.rules.compilation.orchestrator import (
                compile_rules as _compile_entity_rules,
            )

            entity_rules, compiler_evidence, compiler_results = _compile_entity_rules(
                self.source_entities, cfg
            )

        self.rules = sorted(
            entity_rules, key=lambda r: (r.rule_id, r.selector.source_entity_id)
        )

        if compiler_results:
            self.rule_results.extend(compiler_results)
            rule_by_id = {rule.rule_id: rule for rule in self.rules}
            for result in compiler_results:
                rule = rule_by_id.get(result.rule_id)
                source_entity = self.source_by_id.get(result.source_entity_id)
                if rule is None or source_entity is None:
                    continue
                validation = rule_result_to_validation(
                    rule, result, source_entity, None
                )
                self.add_validation_result(validation)

        if compiler_evidence:
            for evidence in compiler_evidence:
                if evidence.entity_id is None:
                    continue
                source_entity = self.source_by_id.get(evidence.entity_id)
                if source_entity is None:
                    continue
                self.add_validation_result(
                    compiler_evidence_to_validation(evidence, source_entity)
                )

    def evaluate_rules(self: "ProjectStateLike") -> None:
        if self.rules and self.source_index and self.target_index:
            ctx = EvalContext(
                source_index=self.source_index,
                target_index=self.target_index,
                matches=self.match_by_source_id,
                config=self._active_config(),
                source_by_id=self.source_by_id,
                target_by_id=self.target_by_id,
            )

            for rule in self.rules:
                if not rule.enabled:
                    continue
                source_entity = self.source_by_id.get(rule.selector.source_entity_id)
                match = self.match_by_source_id.get(rule.selector.source_entity_id)
                if source_entity is None or match is None:
                    continue
                target_entity = (
                    self.target_by_id.get(match.target_id) if match.target_id else None
                )
                from src.core.evaluation import evaluate_rule as _evaluate_rule

                result = _evaluate_rule(rule, source_entity, match, ctx)
                self.rule_results.append(result)
                validation = rule_result_to_validation(
                    rule, result, source_entity, target_entity
                )
                self.add_validation_result(validation)

    def analyze(self: "ProjectStateLike") -> "ProjectStateLike":
        self.build_entity_indexes()
        self.run_matching()
        self.compile_rules()
        self.evaluate_rules()
        return self
