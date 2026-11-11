from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Literal, Mapping, Tuple, cast

# The payload hashing is the one evidence collection uses: a compiler's
# evidence and a collector's of the same payload get the same id.
from pythonarchtesting.core.evidence import canonicalize_payload, evidence_id
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity


def declaration_evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    evidence_type: str,
    payload: Dict[str, Any],
) -> Evidence:
    """The compiler's evidence of type ``evidence_type`` about ``declaration``
    on ``source_entity``, located at the declaration (at the entity when the
    declaration has no line); every marker compiler reports the problems of a
    declaration it drops this way."""
    location = {
        "filepath": source_entity.filepath_rel,
        "lineno": declaration.lineno or source_entity.lineno,
        "col": declaration.col,
    }
    return Evidence(
        evidence_id=evidence_id(evidence_type, payload),
        type=evidence_type,
        source="compiler",
        role="source",
        entity_id=source_entity.canonical_id,
        payload=canonicalize_payload(payload),
        location=location,
    )


def invalid_declaration_evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    decorator: str,
    reason: str,
    params: Dict[str, Any],
) -> Evidence:
    """The evidence that the ``decorator`` marker's ``declaration`` was
    dropped: ``reason`` says which parameter is invalid, ``params`` are the
    parameters as declared."""
    payload = {
        "decorator": decorator,
        "issue": "compiler_invalid_declaration",
        "reason": reason,
        "params": params,
    }
    return declaration_evidence(
        source_entity,
        declaration,
        evidence_type="compiler_invalid_declaration",
        payload=payload,
    )


def invalid_target_evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    decorator: str,
    expected_kind: str = "class",
    key: str = "decorator",
) -> Evidence:
    """The evidence that the ``decorator`` marker, which checks entities of
    ``expected_kind``, was declared on ``source_entity``, which is of
    another kind. ``key`` is the payload key that names the marker: some
    compilers name it ``declaration``, and the payload is kept as it was."""
    payload = {
        key: decorator,
        "issue": "compiler_invalid_target",
        "expected_kind": expected_kind,
        "found_kind": source_entity.kind,
    }
    return declaration_evidence(
        source_entity,
        declaration,
        evidence_type="compiler_invalid_target",
        payload=payload,
    )


@dataclass(frozen=True)
class InvalidParam:
    """A parameter a marker compiler refuses: what the sentinel rule and the
    compiler evidence of the dropped declaration report."""

    param: str
    value: Any
    valid: list[Any] | None
    reason: str

    def fields(self) -> dict[str, Any]:
        """The fields as the keyword arguments of a compiler's ``_drop``."""
        return {
            "param": self.param,
            "value": self.value,
            "valid": self.valid,
            "reason": self.reason,
        }


BOOL_VALUES = [True, False]


def without_none(params: Mapping[str, Any], names: Iterable[str]) -> Dict[str, Any]:
    """``params`` without the ones of ``names`` declared as ``None``: such a
    parameter takes its default, as if it were not declared."""
    omitted = set(names)
    return {
        key: value
        for key, value in params.items()
        if not (value is None and key in omitted)
    }


def bool_problem(params: Mapping[str, Any], name: str) -> InvalidParam | None:
    """Why the logical parameter ``name`` is invalid, ``None`` when it is
    valid: ``True`` or ``False``, or absent or ``None`` for its default. Any
    other value (``"no"``, ``1``) is invalid rather than read for its
    truthiness."""
    value = params.get(name)
    if value is None or isinstance(value, bool):
        return None
    return InvalidParam(
        param=name,
        value=value,
        valid=list(BOOL_VALUES),
        reason=f"{name} must be True or False",
    )


def bool_param(params: Mapping[str, Any], name: str, *, default: bool) -> bool:
    """The logical parameter ``name``: ``default`` when it is absent or
    ``None``. A compiler refuses an invalid one (:func:`bool_problem`) before
    it asks for it, so this never reads a value that is no ``bool``."""
    value = params.get(name)
    return value if isinstance(value, bool) else default


def choice_problem(
    params: Mapping[str, Any],
    name: str,
    choices: Iterable[str],
    *,
    any_case: bool = True,
) -> InvalidParam | None:
    """Why the enumerated parameter ``name`` is invalid, ``None`` when it is
    valid: one of ``choices`` (in any case when ``any_case``), or absent or
    ``None`` for its default. Any other value is invalid rather than replaced
    by the default."""
    valid = sorted(choices)
    value = params.get(name)
    if value is None:
        return None
    if isinstance(value, str) and (value.lower() if any_case else value) in valid:
        return None
    return InvalidParam(
        param=name,
        value=value,
        valid=list(valid),
        reason=f"{name} must be one of: " + ", ".join(valid),
    )


def options_problem(
    params: Mapping[str, Any],
    *,
    bools: Iterable[str] = (),
    choices: Mapping[str, Iterable[str]] | None = None,
) -> InvalidParam | None:
    """The first invalid one of the logical parameters ``bools`` and then of
    the enumerated parameters ``choices`` (name -> valid values, read in any
    case), ``None`` when all are valid."""
    for name in bools:
        problem = bool_problem(params, name)
        if problem is not None:
            return problem
    for name, values in (choices or {}).items():
        problem = choice_problem(params, name, values)
        if problem is not None:
            return problem
    return None


def invalid_param_payload(problem: InvalidParam) -> Dict[str, Any]:
    """The payload keys every marker's evidence of an invalid logical or
    enumerated parameter, or of an invalid severity, has, besides the one
    naming the marker: the issue is ``invalid_<param>``. The value is under
    ``value``, not under the parameter's name, which for ``severity`` would
    set the severity of the evidence itself."""
    return {
        "issue": f"invalid_{problem.param}",
        "param": problem.param,
        "value": problem.value,
        "valid": problem.valid,
        "reason": problem.reason,
    }


def reject_invalid_param(
    source_entity: Entity,
    declaration: DeclarationEntry,
    problem: InvalidParam | None,
    *,
    marker: str,
    rule_id_prefix: str,
    rule_id_suffix: str,
    evidence_type: str = "compiler_invalid_param",
    key: str = "decorator",
    compiler_evidence: List[Evidence] | None = None,
) -> Tuple[List[Any], List[Any], List[Any]] | None:
    """The dropped declaration when ``problem`` is set, else ``None``.

    The declaration gives a ``compiler_invalid_param`` sentinel rule under
    the marker's ``rule_id_prefix`` and one evidence of the marker's
    ``evidence_type``, its payload naming the marker under ``key`` and
    carrying :func:`invalid_param_payload`; both are the ones the marker
    reports its other invalid parameters with. ``compiler_evidence``
    gathered before is kept ahead of it.
    """
    if problem is None:
        return None
    sentinel = build_invalid_param_sentinel_rule(
        source_entity,
        decorator_name=marker,
        rule_id_prefix=rule_id_prefix,
        rule_id_suffix=rule_id_suffix,
        **problem.fields(),
    )
    evidence = declaration_evidence(
        source_entity,
        declaration,
        evidence_type=evidence_type,
        payload={key: marker, **invalid_param_payload(problem)},
    )
    return [sentinel], [*(compiler_evidence or []), evidence], []


SEVERITIES = ("error", "warning", "info")
INVALID_SEVERITY_ISSUE = "invalid_severity"


def severity_problem(params: Dict[str, Any]) -> InvalidParam | None:
    """Why the severity a marker declares is invalid, ``None`` when it is
    valid: one of :data:`SEVERITIES` in any case, or absent or ``None`` for
    the default ``"error"``."""
    raw = params.get("severity")
    if raw is None or (isinstance(raw, str) and raw.lower() in SEVERITIES):
        return None
    return InvalidParam(
        param="severity",
        value=raw,
        valid=list(SEVERITIES),
        reason="severity must be one of: " + ", ".join(SEVERITIES),
    )


def invalid_severity_payload(problem: InvalidParam) -> Dict[str, Any]:
    """The payload keys every marker's evidence of an invalid severity has,
    besides the one naming the marker (:func:`invalid_param_payload`)."""
    return invalid_param_payload(problem)


def reject_invalid_severity(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    marker: str,
    rule_id_prefix: str,
    rule_id_suffix: str,
    evidence_type: str = "compiler_invalid_param",
    key: str = "decorator",
    compiler_evidence: List[Evidence] | None = None,
) -> Tuple[List[Any], List[Any], List[Any]] | None:
    """The dropped declaration when its severity is invalid, else ``None``;
    reported as :func:`reject_invalid_param` reports any invalid parameter."""
    return reject_invalid_param(
        source_entity,
        declaration,
        severity_problem(dict(declaration.params)),
        marker=marker,
        rule_id_prefix=rule_id_prefix,
        rule_id_suffix=rule_id_suffix,
        evidence_type=evidence_type,
        key=key,
        compiler_evidence=compiler_evidence,
    )


def marker_severity(params: Dict[str, Any]) -> Literal["error", "warning", "info"]:
    """The severity a marker declares (``severity=``, any case); ``"error"``
    when it declares none. A compiler drops a declaration with an invalid
    severity (:func:`severity_problem`) before it asks for it, so an invalid
    one here is a bug of the compiler and raises ``ValueError``."""
    problem = severity_problem(params)
    if problem is not None:
        raise ValueError(f"{problem.reason}, not {problem.value!r}")
    raw = params.get("severity")
    if raw is None:
        return "error"
    return cast(Literal["error", "warning", "info"], str(raw).lower())


def with_rule_id_suffix(rule_id: str, suffix: str = "") -> str:
    """Append a deterministic declaration suffix to a rule ID when needed."""
    if not suffix:
        return rule_id
    return f"{rule_id}{suffix}"


def build_invalid_param_sentinel_rule(
    source_entity: Entity,
    *,
    decorator_name: str,
    rule_id_prefix: str,
    param: str,
    value: Any = None,
    valid: list[Any] | None = None,
    reason: str | None = None,
    rule_id_suffix: str = "",
) -> Any:
    """Build a sentinel Rule that surfaces a dropped rule at evaluation time.

    Without this sentinel, an invalid-param diagnostic would emit only
    compiler evidence, leaving the dropped rule invisible in
    ``status_counts``. The sentinel is dispatched to
    :class:`CompilerInvalidParamEvaluator`, which always returns FAILED.

    Parameters
    ----------
    decorator_name:
        Public marker name (e.g. ``"required_factory"``,
        ``"require_method_set"``). Stamped into ``params["decorator"]``
        and used in ``rule.name`` and the message template.
    rule_id_prefix:
        Stable prefix for the sentinel's ``rule_id``, e.g.
        ``"API005/require_method_set/invalid_declaration"``. The ``param``
        name is appended; ``rule_id_suffix`` is appended after that.
    """
    from pythonarchtesting.core.models import Rule, RuleSelector

    selector = RuleSelector(
        source_entity_id=source_entity.canonical_id,
        explicit_target=None,
    )
    params: Dict[str, Any] = {
        "decorator": decorator_name,
        "param": param,
        "value": value,
        "valid": list(valid) if valid is not None else [],
        "compiler_reason": reason,
        "fail_on_unmatched": True,
    }
    if valid:
        fix_hint = f"Use one of: {', '.join(sorted(str(item) for item in valid))}"
    elif reason:
        fix_hint = reason
    else:
        fix_hint = "Provide a valid value for the parameter."
    return Rule(
        rule_id=with_rule_id_suffix(
            f"{rule_id_prefix}/{param}",
            rule_id_suffix,
        ),
        rule_type="compiler_invalid_param",
        name=decorator_name,
        severity="error",
        scope=source_entity.kind,
        evidence_type="static",
        selector=selector,
        params=params,
        message_template=(
            f"{decorator_name} parameter {{details.param}} is invalid; "
            "the rule was dropped at compile time."
        ),
        fix_hints=(fix_hint,),
        enabled=True,
    )


__all__ = [
    "BOOL_VALUES",
    "INVALID_SEVERITY_ISSUE",
    "InvalidParam",
    "SEVERITIES",
    "bool_param",
    "bool_problem",
    "choice_problem",
    "build_invalid_param_sentinel_rule",
    "canonicalize_payload",
    "declaration_evidence",
    "evidence_id",
    "invalid_declaration_evidence",
    "invalid_param_payload",
    "invalid_severity_payload",
    "invalid_target_evidence",
    "marker_severity",
    "options_problem",
    "reject_invalid_param",
    "reject_invalid_severity",
    "severity_problem",
    "with_rule_id_suffix",
    "without_none",
]
