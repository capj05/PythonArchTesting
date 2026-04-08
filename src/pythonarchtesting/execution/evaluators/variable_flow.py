from __future__ import annotations

from collections import deque
from typing import Any

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult
from pythonarchtesting.entities import Entity
from pythonarchtesting.execution.flow_cfg import build_function_cfg
from pythonarchtesting.matching import MatchResult

from .messages import _build_rule_result


class VariableFlowEvaluator:
    """Evaluator for function/method variable-flow rules."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        _ = ctx
        required_stages = [
            str(item)
            for item in list(rule.params.get("stages", []))
            if isinstance(item, str)
        ]
        variable = str(rule.params.get("variable", ""))
        cfg = build_function_cfg(target, variable=variable)
        details: dict[str, Any] = {
            "variable": variable,
            "required_stages": required_stages,
            "source_flow_markers": list(rule.params.get("source_flow_markers", [])),
        }
        if cfg.entry_node_id is None:
            details["reason"] = (
                "target entity does not expose a function body for CFG evaluation"
            )
            details["failure_reason"] = "missing_cfg"
            return _build_rule_result(
                rule,
                source,
                target,
                match,
                "FAILED",
                details,
                (),
            )

        failures: list[dict[str, Any]] = []
        exit_sequences: list[dict[str, Any]] = []
        seen: set[tuple[int, int]] = set()
        queue: deque[tuple[int, int, list[str]]] = deque([(cfg.entry_node_id, 0, [])])

        while queue:
            node_id, progress, observed = queue.popleft()
            state_key = (node_id, progress)
            if state_key in seen:
                continue
            seen.add(state_key)

            node = cfg.nodes[node_id]
            current_progress = progress
            current_observed = list(observed)

            for marker in node.flow_markers:
                stage = marker.stage
                current_observed.append(stage)
                if (
                    current_progress < len(required_stages)
                    and stage == required_stages[current_progress]
                ):
                    current_progress += 1
                    continue
                if stage in required_stages[current_progress + 1 :]:
                    failures.append(
                        {
                            "reason": "out_of_order_stage",
                            "lineno": node.lineno,
                            "observed_stages": current_observed,
                            "missing_stages": required_stages[current_progress:],
                        }
                    )
                    current_progress = -1
                    break
            if current_progress < 0:
                continue

            if not node.successors:
                missing = required_stages[current_progress:]
                exit_record = {
                    "exit_lineno": node.lineno,
                    "observed_stages": current_observed,
                    "matched_count": current_progress,
                    "missing_stages": missing,
                }
                exit_sequences.append(exit_record)
                if missing:
                    failures.append(
                        {
                            "reason": "missing_stages",
                            "lineno": node.lineno,
                            "observed_stages": current_observed,
                            "missing_stages": missing,
                        }
                    )
                continue

            for successor in node.successors:
                queue.append((successor, current_progress, current_observed))

        if failures:
            first_failure = failures[0]
            details.update(
                {
                    "reason": (
                        f"variable '{variable}' misses or misorders required stages "
                        f"on an exit-reaching path"
                    ),
                    "failure_reason": first_failure["reason"],
                    "missing_stages": first_failure.get("missing_stages", []),
                    "first_failing_path_exit_line": first_failure.get("lineno", 0),
                    "observed_path_sequences": exit_sequences,
                    "target_flow_locations": [
                        {
                            "lineno": node.lineno,
                            "col": node.col,
                            "stages": [marker.stage for marker in node.flow_markers],
                        }
                        for node in cfg.nodes.values()
                        if node.flow_markers
                    ],
                }
            )
            return _build_rule_result(
                rule,
                source,
                target,
                match,
                "FAILED",
                details,
                (),
            )

        details.update(
            {
                "reason": "Variable flow requirement satisfied.",
                "failure_reason": None,
                "missing_stages": [],
                "first_failing_path_exit_line": None,
                "observed_path_sequences": exit_sequences,
                "target_flow_locations": [
                    {
                        "lineno": node.lineno,
                        "col": node.col,
                        "stages": [marker.stage for marker in node.flow_markers],
                    }
                    for node in cfg.nodes.values()
                    if node.flow_markers
                ],
            }
        )
        return _build_rule_result(rule, source, target, match, "OK", details, ())


__all__ = ["VariableFlowEvaluator"]
