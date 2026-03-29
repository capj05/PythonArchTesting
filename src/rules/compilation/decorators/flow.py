from __future__ import annotations

from typing import Any, List, Literal, Tuple, cast

from src.config import Config
from src.core.models import Evidence
from src.entities import DeclarationEntry, Entity

from ..common import canonicalize_payload, evidence_id, with_rule_id_suffix
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
    return Evidence(
        evidence_id=evidence_id("compiler_invalid_flow_declaration", payload),
        type="compiler_invalid_flow_declaration",
        source="compiler",
        role="source",
        entity_id=source_entity.canonical_id,
        payload=canonicalize_payload(payload),
        location={
            "filepath": source_entity.filepath_rel,
            "lineno": declaration.lineno or source_entity.lineno,
            "col": declaration.col,
        },
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
    from src.core.models import Rule, RuleSelector

    _ = cfg
    compiler_evidence: list[Evidence] = []
    params_kwargs = dict(declaration.params)

    if source_entity.kind not in {"function", "method"}:
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                payload={
                    "declaration": "enforce_flow",
                    "issue": "compiler_invalid_target",
                    "expected_kind": "function_or_method",
                    "found_kind": source_entity.kind,
                },
            )
        )
        return [], compiler_evidence, []

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
        return [], compiler_evidence, []

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
            return [], compiler_evidence, []
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
        return [], compiler_evidence, []

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
            return [], compiler_evidence, []

    base_severity_raw = str(params_kwargs.get("severity", "error")).lower()
    if base_severity_raw in {"error", "warning", "info"}:
        base_severity = cast(Literal["error", "warning", "info"], base_severity_raw)
    else:
        base_severity = "error"

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


__all__ = ["compile_enforce_flow"]
