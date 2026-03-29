"""
Lightweight validation helpers for report schema v2.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _expect(condition: bool, message: str, errors: List[str]) -> None:
    if not condition:
        errors.append(message)


def validate_report_schema_v2(report: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(report, dict):
        return ["report must be a dict"]

    _expect(report.get("schema_version") == "2", "schema_version must be '2'", errors)
    _expect("generated_at" in report, "generated_at is required", errors)
    _expect(isinstance(report.get("run"), dict), "run must be a dict", errors)
    _expect(
        isinstance(report.get("exit_code"), int), "exit_code must be an int", errors
    )

    if "matching" in report:
        matching = report.get("matching")
        _expect(isinstance(matching, dict), "matching must be a dict", errors)
        if isinstance(matching, dict):
            _expect(
                isinstance(matching.get("matches"), list),
                "matching.matches must be a list",
                errors,
            )

    if "results" in report:
        _expect(
            isinstance(report.get("results"), list), "results must be a list", errors
        )
        results = report.get("results")
        if isinstance(results, list):
            required_result_fields = (
                "result_id",
                "project_id",
                "rule_id",
                "category",
                "severity",
                "status",
                "source",
                "target",
                "message",
                "evidence",
                "details",
            )
            for idx, item in enumerate(results):
                if not isinstance(item, dict):
                    errors.append(f"results[{idx}] must be a dict")
                    continue
                for field in required_result_fields:
                    if field not in item:
                        errors.append(f"results[{idx}].{field} is required")

    if "targets" in report:
        targets = report.get("targets")
        _expect(isinstance(targets, list), "targets must be a list", errors)
        if isinstance(targets, list):
            for idx, target in enumerate(targets):
                if not isinstance(target, dict):
                    errors.append(f"targets[{idx}] must be a dict")
                    continue
                _expect(
                    isinstance(target.get("target_id"), str),
                    f"targets[{idx}].target_id must be a string",
                    errors,
                )
                _expect(
                    isinstance(target.get("target_path"), str),
                    f"targets[{idx}].target_path must be a string",
                    errors,
                )
                _expect(
                    isinstance(target.get("matching"), dict),
                    f"targets[{idx}].matching must be a dict",
                    errors,
                )
                _expect(
                    isinstance(target.get("results"), list),
                    f"targets[{idx}].results must be a list",
                    errors,
                )
                _expect(
                    isinstance(target.get("exit_code"), int),
                    f"targets[{idx}].exit_code must be an int",
                    errors,
                )
                if "summary" in target:
                    _expect(
                        isinstance(target.get("summary"), dict),
                        f"targets[{idx}].summary must be a dict",
                        errors,
                    )

    if "summary" in report:
        _expect(
            isinstance(report.get("summary"), dict), "summary must be a dict", errors
        )

    return errors


__all__ = ["validate_report_schema_v2"]
