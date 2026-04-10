from __future__ import annotations

from typing import TYPE_CHECKING

from ._orchestrator import analyze as analyze_stage
from ._orchestrator import compile_rules as compile_rules_stage
from ._orchestrator import evaluate_rules as evaluate_rules_stage

if TYPE_CHECKING:
    from ._typing import RulesStateLike


class ProjectStateRulesMixin:
    """Rule compilation + evaluation + wiring to ValidationResult."""

    def compile_rules(self: "RulesStateLike") -> None:
        self._ensure_context_config()
        self._stores.rules.reset()
        compile_rules_stage(self._context, self._stores, self.add_validation_result)

    def evaluate_rules(self: "RulesStateLike") -> None:
        self._ensure_context_config()
        evaluate_rules_stage(self._context, self._stores, self.add_validation_result)

    def analyze(self: "RulesStateLike") -> "RulesStateLike":
        self._ensure_context_config()
        analyze_stage(
            self._context,
            self._stores,
            self._services,
            self.add_validation_result,
        )
        return self
