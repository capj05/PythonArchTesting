from __future__ import annotations

import json
from typing import Any

from src.rules.compilation.declarations import (
    is_invalid_annotation_declaration,
    normalize_declaration_entries,
)
from src.state.validation import ValidationResult
from src.state_multi import RunState


def _entry_diagnostic(entity: Any, entry: Any) -> dict[str, Any]:
    invalid = is_invalid_annotation_declaration(entry)
    return {
        "category": "invalid_declaration" if invalid else "declaration_warning",
        "severity": "error" if invalid else "warning",
        "check_type": (
            "compiler_invalid_declaration"
            if invalid
            else "annotation_declaration_warning"
        ),
        "entity": {
            "id": entity.canonical_id,
            "kind": entity.kind,
            "name": entity.name,
            "qualname": entity.qualname,
            "module_path": entity.module_path,
        },
        "location": {
            "filepath": entity.filepath_rel,
            "lineno": int(entry.lineno or entity.lineno or 0) or None,
            "col": int(entry.col or 0),
        },
        "declaration": {
            "kind": entry.kind,
            "raw": entry.raw,
            "params": dict(entry.params),
            "base_annotation": entry.base_annotation,
            "container": entry.container,
        },
        "issues": [dict(issue) for issue in entry.unsupported],
    }


def _validation_diagnostic(validation: ValidationResult) -> dict[str, Any]:
    details = dict(validation.details or {})
    return {
        "category": "source_error",
        "severity": "error",
        "check_type": validation.check_type,
        "entity": {
            "id": None,
            "kind": None,
            "name": validation.src_function_name or "",
            "qualname": validation.src_function_name or "",
            "module_path": validation.src_package or "",
        },
        "location": {
            "filepath": validation.src_file,
            "lineno": validation.src_line_num,
            "col": details.get("offset"),
        },
        "declaration": None,
        "issues": [],
        "description": validation.description,
        "details": details,
    }


def collect_declaration_diagnostics(run_state: RunState) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []

    for entity in run_state.source_entities:
        for entry in normalize_declaration_entries(entity):
            if not entry.unsupported and not is_invalid_annotation_declaration(entry):
                continue
            diagnostics.append(_entry_diagnostic(entity, entry))

    for validation in run_state.compiler_validations:
        if validation.check_type == "compiler_invalid_declaration":
            continue
        if not validation.check_type.startswith("extraction/"):
            continue
        diagnostics.append(_validation_diagnostic(validation))

    diagnostics.sort(
        key=lambda item: (
            str(item["location"].get("filepath") or ""),
            int(item["location"].get("lineno") or 0),
            int(item["location"].get("col") or 0),
            str(item.get("check_type") or ""),
            str((item.get("declaration") or {}).get("raw") or ""),
        )
    )
    return diagnostics


def summarize_declaration_diagnostics(
    run_state: RunState, diagnostics: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "source_path": str(run_state.source_path),
        "reference_modules": list(run_state.reference_modules),
        "source_entities": len(run_state.source_entities),
        "files_scanned": len(
            {
                str(item.filepath_rel)
                for item in run_state.source_entities
                if getattr(item, "filepath_rel", "")
            }
        ),
        "diagnostics_total": len(diagnostics),
        "invalid_declarations": sum(
            1 for item in diagnostics if item["category"] == "invalid_declaration"
        ),
        "warning_declarations": sum(
            1 for item in diagnostics if item["category"] == "declaration_warning"
        ),
        "syntax_errors": sum(
            1 for item in diagnostics if item["check_type"] == "extraction/syntax_error"
        ),
        "source_resolution_errors": sum(
            1
            for item in diagnostics
            if item["check_type"] == "extraction/source_resolution"
        ),
        "errors_total": sum(1 for item in diagnostics if item["severity"] == "error"),
        "warnings_total": sum(
            1 for item in diagnostics if item["severity"] == "warning"
        ),
    }


def get_declaration_validation_exit_code(run_state: RunState) -> int:
    diagnostics = collect_declaration_diagnostics(run_state)
    return 1 if any(item["severity"] == "error" for item in diagnostics) else 0


def build_declaration_validation_report(
    run_state: RunState, output_format: str = "json"
) -> str:
    diagnostics = collect_declaration_diagnostics(run_state)
    summary = summarize_declaration_diagnostics(run_state, diagnostics)
    payload = {
        "mode": "validate-declarations",
        "summary": summary,
        "diagnostics": diagnostics,
    }
    if output_format == "json":
        return json.dumps(payload, indent=2, sort_keys=True)
    raise ValueError(
        f"Unsupported declaration validation output format: {output_format}"
    )


__all__ = [
    "build_declaration_validation_report",
    "collect_declaration_diagnostics",
    "get_declaration_validation_exit_code",
    "summarize_declaration_diagnostics",
]
