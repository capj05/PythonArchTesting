"""
Validation result classes and status enums for the project state.
"""

import time
from dataclasses import dataclass, field
from string import Template
from textwrap import dedent
from typing import Any, Dict, Optional

from pythonarchtesting.constants import ValidationConstants
from pythonarchtesting.core.models import Evidence, Rule, RuleResult
from pythonarchtesting.entities import Entity


@dataclass
class ValidationResult:
    """
    Represents the result of a validation check.

    Attributes:
        status: Status of the validation (OK/FAILED/WARNING/ERROR)
        description: Description of the validation result, especially for failures
        function_name: Name of the validated function
        package: Package or module the function belongs to
        source_line: Line number in source (if available)
        source_file: Source file path (if available)
        check_type: Type of check performed (e.g., "type_check", "dependency_check")
        timestamp: When the validation was performed
        details: Additional details specific to the validation type
        error_code: Optional error code for categorization
        suggestion: Optional suggestion for fixing the issue
        original_error: Optional original exception that caused this result
    """

    status: ValidationConstants.ValidationStatus
    description: str
    check_type: str
    src_function_name: str
    src_package: Optional[str] = None
    src_line_num: Optional[int] = None
    src_file: Optional[str] = None
    target_function_name: Optional[str] = None
    target_package: Optional[str] = None
    project_name: Optional[str] = None  # New field for multi-project support
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None
    suggestion: Optional[str] = None
    original_error: Optional[Exception] = None

    def get_formatted_str(self) -> str:
        template = Template(dedent("""
                Validation result:
                - status: $status
                - description: $description
                - src_function_name: $src_function_name
                - src_package: $src_package
                - source_line: $src_line_num
                - source_file: $src_file
                - check_type: $check_type
                - target_function_name: $target_function_name
                - target_package: $target_package
                - project_name: $project_name
                - timestamp: $timestamp
                - details: $details
                - error_code: $error_code
                - suggestion: $suggestion
                """))
        return template.substitute(self.__dict__, timestamp=time.ctime(self.timestamp))

    def get_error_message(self) -> str:
        """Get formatted error message with context."""
        parts = [self.description]

        if self.project_name:
            parts.append(f"Project: {self.project_name}")
        if self.error_code:
            parts.append(f"[{self.error_code}]")
        if self.suggestion:
            parts.append(f"Hint: {self.suggestion}")
        if self.src_file:
            location = self.src_file
            if self.src_line_num:
                location += f":{self.src_line_num}"
            parts.append(f"Location: {location}")

        return " | ".join(parts)


def _evidence_to_dict(evidence: Evidence) -> Dict[str, Any]:
    return {
        "evidence_id": evidence.evidence_id,
        "type": evidence.type,
        "source": evidence.source,
        "role": evidence.role,
        "entity_id": evidence.entity_id,
        "payload": evidence.payload,
        "location": evidence.location,
    }


def compiler_evidence_to_validation(
    evidence: Evidence,
    source_entity: Entity,
    *,
    project_name: Optional[str] = None,
) -> ValidationResult:
    """Convert compiler evidence into a reportable validation result."""
    payload_severity = str(evidence.payload.get("severity") or "").lower()
    if payload_severity == "error":
        status = ValidationConstants.ValidationStatus.ERROR
    elif payload_severity == "info":
        status = ValidationConstants.ValidationStatus.OK
    else:
        status = ValidationConstants.ValidationStatus.WARNING
    return ValidationResult(
        status=status,
        description=str(
            evidence.payload.get("message")
            or evidence.payload.get("issue")
            or evidence.type
        ),
        check_type=evidence.type,
        src_function_name=source_entity.name,
        src_package=source_entity.module_path,
        src_file=source_entity.filepath_rel,
        src_line_num=int(
            (evidence.location or {}).get("lineno") or source_entity.lineno or 0
        )
        or None,
        project_name=project_name,
        details={"evidence": [_evidence_to_dict(evidence)]},
        suggestion=str(evidence.payload.get("suggestion") or "") or None,
    )


def rule_result_to_validation(
    rule: Rule,
    result: RuleResult,
    source_entity: Entity,
    target_entity: Optional[Entity],
) -> ValidationResult:
    status_map = {
        "OK": ValidationConstants.ValidationStatus.OK,
        "FAILED": ValidationConstants.ValidationStatus.FAILED,
        "SKIPPED": ValidationConstants.ValidationStatus.WARNING,
        "ERROR": ValidationConstants.ValidationStatus.ERROR,
    }

    status = status_map.get(result.status, ValidationConstants.ValidationStatus.ERROR)
    details = dict(result.details)
    details.update(
        {
            "rule_id": rule.rule_id,
            "rule_type": rule.rule_type,
            "source_entity_id": result.source_entity_id,
            "target_entity_id": result.target_entity_id,
            "match_status": result.match_status,
            "confidence": result.confidence,
            "evidence": [_evidence_to_dict(ev) for ev in result.evidence],
            "params": rule.params,
        }
    )
    activation_source = getattr(rule, "activation_source", None)
    if isinstance(activation_source, str) and activation_source:
        details["activation_source"] = activation_source

    if result.status == "SKIPPED":
        details.setdefault("skipped", True)

    src_function_name = source_entity.name
    src_package = source_entity.module_path
    src_file = source_entity.filepath_rel
    src_line_num = source_entity.lineno
    target_function_name = target_entity.name if target_entity else None
    target_package = target_entity.module_path if target_entity else None

    return ValidationResult(
        status=status,
        description=result.message,
        check_type=rule.rule_type,
        src_function_name=src_function_name,
        src_package=src_package,
        src_file=src_file,
        src_line_num=src_line_num,
        target_function_name=target_function_name,
        target_package=target_package,
        details=details,
    )
