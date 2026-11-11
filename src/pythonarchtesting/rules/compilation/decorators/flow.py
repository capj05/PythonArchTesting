from __future__ import annotations

from typing import Any, List, Literal, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import (
    declaration_evidence,
    drop_with_sentinel,
    marker_severity,
    reject_invalid_severity,
    reject_misplaced,
    with_rule_id_suffix,
)
from ..declarations import (
    is_invalid_annotation_declaration,
    normalize_declaration_entries,
)


def _evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    payload: dict[str, Any],
) -> Evidence:
    return declaration_evidence(
        source_entity,
        declaration,
        evidence_type="compiler_invalid_flow_declaration",
        payload=payload,
    )


def _valid_flow_entries(source_entity: Entity) -> list[DeclarationEntry]:
    return [
        entry
        for entry in normalize_declaration_entries(source_entity)
        if entry.kind == "flow"
        and entry.surface == "statement"
        and not is_invalid_annotation_declaration(entry)
    ]


def compile_enforce_flow(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    from pythonarchtesting.core.models import Rule, RuleSelector

    _ = cfg
    compiler_evidence: list[Evidence] = []
    # An argument given as None is left out: cases=None is no runtime check.
    params_kwargs = {
        key: value for key, value in declaration.params.items() if value is not None
    }

    runtime = "cases" in params_kwargs
    drop: dict[str, Any] = {
        "marker": "enforce_flow",
        "rule_id_prefix": (
            "FLW002/enforce_flow_runtime/invalid_declaration"
            if runtime
            else "FLW001/enforce_flow/invalid_declaration"
        ),
        "rule_id_suffix": rule_id_suffix,
    }
    if source_entity.kind not in {"function", "method"}:
        return reject_misplaced(
            source_entity,
            _evidence(
                source_entity,
                declaration,
                payload={
                    "declaration": "enforce_flow",
                    "issue": "compiler_invalid_target",
                    "expected_kind": "function_or_method",
                    "found_kind": source_entity.kind,
                },
            ),
            **drop,
            valid=["function", "method"],
            compiler_evidence=compiler_evidence,
        )
    stages_raw = params_kwargs.get("stages", [])
    stages = (
        [str(item) for item in stages_raw if isinstance(item, str)]
        if isinstance(stages_raw, list)
        else []
    )
    if not stages or len(stages) != len(stages_raw):
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                payload={
                    "declaration": "enforce_flow",
                    "issue": "invalid_stages",
                    "stages": stages_raw,
                },
            )
        )
        return drop_with_sentinel(
            source_entity,
            compiler_evidence,
            **drop,
            param="stages",
            value=stages_raw,
            reason="stages must be a non-empty list of stage names",
        )

    flow_entries = _valid_flow_entries(source_entity)
    if not flow_entries:
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                payload={
                    "declaration": "enforce_flow",
                    "issue": "missing_source_flow_markers",
                },
            )
        )
        return [], compiler_evidence, []

    variable = params_kwargs.get("variable")
    variables = sorted(
        {
            str(entry.params.get("variable"))
            for entry in flow_entries
            if isinstance(entry.params.get("variable"), str)
            and str(entry.params.get("variable")).strip()
        }
    )
    if variable is None:
        if len(variables) == 1:
            variable = variables[0]
        else:
            compiler_evidence.append(
                _evidence(
                    source_entity,
                    declaration,
                    payload={
                        "declaration": "enforce_flow",
                        "issue": "ambiguous_variable",
                        "variables": variables,
                    },
                )
            )
            return drop_with_sentinel(
                source_entity,
                compiler_evidence,
                **drop,
                param="variable",
                reason=(
                    "variable must be given when the flow markers do not "
                    "track exactly one variable"
                ),
            )
    elif not isinstance(variable, str) or not variable.strip():
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                payload={
                    "declaration": "enforce_flow",
                    "issue": "invalid_variable",
                    "variable": variable,
                },
            )
        )
        return drop_with_sentinel(
            source_entity,
            compiler_evidence,
            **drop,
            param="variable",
            value=variable,
            reason="variable must be a non-empty string",
        )

    selected_variable = str(variable).strip()
    selected_flow_entries = [
        entry
        for entry in flow_entries
        if entry.params.get("variable") == selected_variable
    ]
    if not selected_flow_entries:
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                payload={
                    "declaration": "enforce_flow",
                    "issue": "missing_source_flow_track",
                    "variable": selected_variable,
                },
            )
        )
        return [], compiler_evidence, []

    for entry in selected_flow_entries:
        stage = entry.params.get("stage")
        if not isinstance(stage, str) or not stage.strip():
            compiler_evidence.append(
                _evidence(
                    source_entity,
                    entry,
                    payload={
                        "declaration": "flow",
                        "issue": "invalid_stage",
                        "stage": stage,
                    },
                )
            )
            return drop_with_sentinel(
                source_entity,
                compiler_evidence,
                **drop,
                param="stage",
                value=stage,
                reason="every flow marker of the tracked variable needs a stage",
            )

    rejected = reject_invalid_severity(
        source_entity,
        declaration,
        **drop,
        evidence_type="compiler_invalid_flow_declaration",
        key="declaration",
        compiler_evidence=compiler_evidence,
    )
    if rejected is not None:
        return rejected

    base_severity = marker_severity(params_kwargs)

    source_flow_markers = [
        {
            "stage": str(entry.params.get("stage")),
            "variable": str(entry.params.get("variable")),
            "anchor_lineno": int(entry.params.get("anchor_lineno", 0) or 0),
            "anchor_col": int(entry.params.get("anchor_col", 0) or 0),
            "anchor_kind": str(entry.params.get("anchor_kind", "")),
            "statement_order": int(entry.params.get("statement_order", 0) or 0),
        }
        for entry in selected_flow_entries
    ]

    if runtime:
        return _compile_runtime_flow(
            source_entity,
            declaration,
            stages=stages,
            variable=selected_variable,
            flow_entries=selected_flow_entries,
            severity=base_severity,
            rule_id_suffix=rule_id_suffix,
        )

    rule = Rule(
        rule_id=with_rule_id_suffix("FLW001/enforce_flow/v1", rule_id_suffix),
        rule_type="variable_flow",
        name="enforce_flow",
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params={
            "stages": stages,
            "variable": selected_variable,
            "source_flow_markers": source_flow_markers,
            "fail_on_unmatched": True,
        },
        message_template=(
            "Variable flow mismatch for {target.module_path}:{target.qualname}: "
            "{details.reason}"
        ),
        fix_hints=(
            "Add statement-level flow markers for the tracked variable "
            "on every exit-reaching path.",
            "Keep required stages in order for the selected variable track.",
        ),
        enabled=True,
    )

    return [rule], compiler_evidence, []


def _compile_runtime_flow(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    stages: list[str],
    variable: str,
    flow_entries: list[DeclarationEntry],
    severity: Literal["error", "warning", "info"],
    rule_id_suffix: str,
) -> Tuple[List[Any], List[Any], List[Any]]:
    """Compile ``enforce_flow(..., cases=[...])`` into a runtime rule.

    Each stage's flow marker sits on the line after the statement it labels,
    so the statement spans from its anchor line to the line before the marker.
    The runtime check records the project functions called while that span
    runs, which identify the stage in a target that carries no markers.
    """
    from pythonarchtesting.core.models import Rule, RuleSelector

    from ..common import build_invalid_param_sentinel_rule

    params_kwargs = dict(declaration.params)
    from .runtime_structure import runtime_cases_problem

    problem = runtime_cases_problem(params_kwargs, source_entity.kind, "enforce_flow")
    if problem is not None:
        param, reason = problem
        sentinel = build_invalid_param_sentinel_rule(
            source_entity,
            decorator_name="enforce_flow",
            rule_id_prefix="FLW002/enforce_flow_runtime/invalid_declaration",
            param=param,
            reason=reason,
            rule_id_suffix=rule_id_suffix,
        )
        payload = {
            "declaration": "enforce_flow",
            "issue": "compiler_invalid_param",
            "param": param,
            "reason": reason,
        }
        return [sentinel], [_evidence(source_entity, declaration, payload=payload)], []

    spans = []
    for entry in flow_entries:
        stage = str(entry.params.get("stage"))
        if stage not in stages:
            continue
        anchor = int(entry.params.get("anchor_lineno", 0) or 0)
        marker_line = int(entry.lineno or anchor)
        spans.append(
            {
                "stage": stage,
                "start": anchor,
                "end": max(anchor, marker_line - 1),
                "variable": variable,
            }
        )

    rule = Rule(
        rule_id=with_rule_id_suffix("FLW002/enforce_flow_runtime/v1", rule_id_suffix),
        rule_type="runtime_flow",
        name="enforce_flow",
        severity=severity,
        scope=source_entity.kind,
        evidence_type="runtime",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params={
            "stages": stages,
            "variable": variable,
            "spans": spans,
            "cases": params_kwargs["cases"],
            "init": params_kwargs.get("init"),
            "timeout_s": float(params_kwargs.get("timeout_s", 5.0)),
            "fail_on_unmatched": True,
        },
        message_template=(
            "enforce_flow (runtime) for "
            "{target.module_path}:{target.qualname}: {details.summary}"
        ),
        fix_hints=(
            "Run the stages in the reference's order: call the project "
            "function each stage uses before those of the later stages.",
            "Runs only with --dynamic; without it the rule is SKIPPED.",
        ),
        enabled=True,
    )
    return [rule], [], []


__all__ = ["compile_enforce_flow"]
