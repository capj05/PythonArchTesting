"""Classify the failures of a report by the typical errors of a principle.

Each fact of a failed result (``details.facts``, aligned 1:1 with
``details.violations``) becomes one ``Finding``: the catalogue error of the
failing marker whose declared ``signature`` matches the fact on every key it
declares (of several, the one declaring the most keys; ties in catalogue
order), or an unclassified finding (``error_id`` ``None``) when none does.
A failure without facts, and any ``ERROR`` result, is no verdict on the code:
one *not judged* finding (``not_judged``) carrying its ``reason`` (the
result's ``details.reason``) and its message.

Two errors are the tool's own, the same for every principle (``BUILTIN_ERRORS``):

- ``missing_required_entity``: a reference entity the rules require has no
  counterpart in the submission (``details.reason``
  ``required_target_missing`` with match status ``unmatched``), or a class a
  rule's cases construct (``{"$new": "inventory.Inventory"}``) that the
  submission lacks (a ``case_setup_failed`` result whose case names it,
  ``unresolved``). A violation: the submission does not keep the
  assignment's protocol. ``classify_target`` gives one finding per entity,
  however many rules require it. An entity paired with less than certainty
  (``ambiguous``, ``low_confidence``) is no such finding: the submission may
  have it, so it is not judged (``ambiguous_match``, ``low_confidence_match``).
- ``syntax_error``: a file of the submission does not parse. No verdict
  (reason ``syntax_error``); ``classify_target`` then drops what may follow
  from the code it could not read (entities without a counterpart, checks
  that could not run), but keeps the violations found in the code it could.

Deterministic: no LLM decides anything here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Optional, cast

from pythonarchtesting.principles.catalog import (
    Principle,
    PrincipleError,
    fact_signature,
    signature_matches,
)
from pythonarchtesting.report.ir.summary import VIOLATION_STATUSES

# The tool's own error ids (``catalog.RESERVED_ERROR_IDS``).
MISSING_REQUIRED_ENTITY = "missing_required_entity"
SYNTAX_ERROR = "syntax_error"
# ``details.reason`` of a rule whose reference entity has no counterpart.
_REQUIRED_TARGET_MISSING = "required_target_missing"
# ``details.reason`` of a rule whose case could not be prepared.
_CASE_SETUP_FAILED = "case_setup_failed"
# The not judged reason of an entity paired with less than certainty, by the
# match status.
_UNCERTAIN_MATCHES = {
    "ambiguous": "ambiguous_match",
    "low_confidence": "low_confidence_match",
}
# The rule id of a file that does not parse.
_SYNTAX_RULE = "extraction/syntax_error"
BUILTIN_ERRORS = {
    MISSING_REQUIRED_ENTITY: PrincipleError(
        id=MISSING_REQUIRED_ENTITY,
        title="a function or class the assignment prescribes is missing",
        why=(
            "The assignment prescribes this function or class: its name and how "
            "it is called. Nothing in the submission could be paired with it, so "
            "the submission does not keep the assignment's protocol and the "
            "checks on it could not run."
        ),
        fix=(
            "Give the function or class the name, the place and the parameters "
            "the assignment prescribes."
        ),
    ),
    SYNTAX_ERROR: PrincipleError(
        id=SYNTAX_ERROR,
        title="a file of the submission does not parse",
        why=(
            "Python cannot read the file, so none of the submission's code can "
            "run or be checked: it gets no verdict until the file parses."
        ),
        fix=(
            "Correct the syntax at the reported line; the message says what "
            "Python expected there."
        ),
    ),
}
# How a write changed the attribute (``change`` of a ``write`` fact), in words.
_CHANGES = {
    "assigned": "assigns it",
    "mutated": "changes its contents",
    "deleted": "deletes it",
    "bypassed": "assigns it past `__setattr__`",
}
_FACT_KEYS = (
    "caller",
    "callee",
    "module",
    "class",
    "attribute",
    "expected_base",
    "creator",
    "expected",
)
# Callees a beginner knows by their bare name, not by their module.
_BARE_CALLEES = {
    "builtins:print": "print",
    "builtins:input": "input",
    "io:open": "open",
    "builtins:isinstance": "isinstance",
    "builtins:type": "type",
}


class _Placeholders(dict):
    """Values for ``str.format_map``; a missing placeholder reads ``?``."""

    def __missing__(self, key: str) -> str:
        return "?"


@dataclass(frozen=True)
class Finding:
    """One violation of a failed result, classified by the principle's errors,
    or one result that gave no verdict on the code (``reason`` set).

    ``error_id`` is ``None`` for an unclassified violation and for a not
    judged finding (but ``syntax_error``, which is both); ``title``, ``what``,
    ``why`` and ``fix`` are then ``None`` too. ``what`` is the error's template
    filled from the result and the fact (``fill_what``), or for a built-in
    error (``BUILTIN_ERRORS``) its sentence."""

    error_id: Optional[str]
    title: Optional[str]
    why: Optional[str]
    fix: Optional[str]
    facts: Mapping[str, Any] = field(hash=False)
    rule: str
    target: Optional[str]
    text: str
    what: Optional[str] = None
    reason: Optional[str] = None

    @property
    def not_judged(self) -> bool:
        """The result gave no verdict on the code (it could not run, the
        entity has no counterpart, the rule errored)."""
        return self.reason is not None

    def to_dict(self, brief: bool = False) -> dict[str, Any]:
        """JSON-able and compact: unset fields are left out, but ``error_id``
        always appears (``None`` marks an unclassified violation, or with
        ``not_judged`` a result without a verdict). ``brief`` leaves out the
        error's ``title``, ``why`` and ``fix``, which a caller lists once, and
        for a classified finding the report's ``text``, which ``what`` states."""
        data: dict[str, Any] = {"error_id": self.error_id}
        if self.not_judged:
            data["not_judged"] = True
            data["reason"] = self.reason
        for key, value in (
            ("title", None if brief else self.title),
            ("what", self.what),
            ("why", None if brief else self.why),
            ("fix", None if brief else self.fix),
            ("rule", self.rule),
            ("target", self.target),
            ("text", None if brief and self.what is not None else self.text),
        ):
            if value is not None:
                data[key] = value
        if self.facts:
            data["facts"] = dict(self.facts)
        return data


def callee_short(callee: str) -> str:
    """``builtins:print`` as ``print()``, ``grades:average`` as ``grades.average()``."""
    return f"{_BARE_CALLEES.get(callee, callee.replace(':', '.'))}()"


def fill_what(template: str, result: Mapping[str, Any], fact: Mapping[str, Any]) -> str:
    """An error's ``what`` with its placeholders (``PLACEHOLDERS``) filled from
    the failed result's target and one of its facts; a value the result or the
    fact lacks reads ``?``."""
    target = result.get("target") or {}
    values = _Placeholders(
        function=target.get("qualname") or "?",
        file=target.get("file") or "?",
        line=target.get("line") or "?",
        fact_file=fact.get("file") or "?",
        fact_line=fact.get("line") or "?",
        via_last=(fact.get("via") or ["?"])[-1],
        via_first_line=fact.get("origin_line") or "?",
    )
    values.update({key: fact[key] for key in _FACT_KEYS if fact.get(key) is not None})
    if fact.get("static") and fact.get("caller"):
        # Found statically in a function no case runs (``cover_module``): the
        # function is that one, not the entity whose rule read it.
        values["function"] = str(fact["caller"]).rpartition(":")[2]
        values["file"] = fact.get("file") or "?"
        values["line"] = fact.get("function_line") or "?"
    if fact.get("callee") is not None:
        values["callee_short"] = callee_short(str(fact["callee"]))
    if fact.get("change") is not None:
        values["change"] = _CHANGES.get(fact["change"], fact["change"])
    if fact.get("concrete_methods") is not None:
        values["concrete_methods"] = ", ".join(map(str, fact["concrete_methods"]))
    return template.format_map(values)


def rule_marker(rule_id: str) -> str:
    """The marker of a rule id such as ``DYN003/forbid_foreign_writes/v1``."""
    parts = rule_id.split("/")
    return parts[1] if len(parts) > 1 else rule_id


def principle_markers(principle: Principle) -> set[str]:
    """The markers whose results judge the principle: its checks' markers and
    the markers that detect its errors."""
    return {check.marker for check in principle.checks} | {
        error.detected_by for error in principle.errors if error.detected_by
    }


def choose_error(
    principle: Principle, rule_id: str, fact: Mapping[str, Any]
) -> Optional[PrincipleError]:
    """The catalogue error of the marker of ``rule_id`` whose signature matches
    the fact on every key it declares; the one declaring the most keys wins,
    ties in catalogue order. ``None`` when none matches."""
    marker = rule_marker(rule_id)
    observed = fact_signature(fact)
    best: Optional[PrincipleError] = None
    best_keys = -1
    for error in principle.errors:
        if error.detected_by != marker or error.signature is None:
            continue
        declared = error.signature.as_dict()
        if signature_matches(declared, observed) and len(declared) > best_keys:
            best, best_keys = error, len(declared)
    return best


def _qualified(entity: Any) -> Optional[str]:
    if not isinstance(entity, Mapping) or not entity.get("qualname"):
        return None
    module = entity.get("module")
    return f"{module}:{entity['qualname']}" if module else str(entity["qualname"])


def result_entity(result: Mapping[str, Any]) -> Optional[str]:
    """The entity a result is about, as ``module:qualname``: the target's, or
    the reference's when the target has none (an unmatched entity: the report
    then gives a target whose fields are all ``None``)."""
    for entity in (
        result.get("target"),
        (result.get("locations") or {}).get("source"),
        result.get("source"),
    ):
        name = _qualified(entity)
        if name is not None:
            return name
    return None


def _unclassified(
    result: Mapping[str, Any], fact: Mapping[str, Any], text: str
) -> Finding:
    return Finding(
        error_id=None,
        title=None,
        why=None,
        fix=None,
        facts=dict(fact),
        rule=str(result.get("rule_id")),
        target=result_entity(result),
        text=text,
    )


def not_judged_reason(result: Mapping[str, Any]) -> str:
    """Why a failed or errored result gives no verdict on the code: the
    result's ``details.reason``, else ``error`` (an ``ERROR`` result) or
    ``no_facts`` (a failure that states no violation)."""
    details = result.get("details") or {}
    reason = str(details.get("reason") or "")
    if reason:
        return reason
    return "error" if result.get("status") == "ERROR" else "no_facts"


def mapping_name(entity_id: str) -> tuple[str, str]:
    """The name a mapping gives a canonical entity id (``shop.sell``; the
    package itself is ``__init__``), and the entity's kind."""
    parts = str(entity_id).split(":")
    module, qualname, kind = parts[-4], parts[-3], parts[-2]
    if kind == "module":
        return module or "__init__", kind
    return f"{module or '__init__'}.{qualname}", kind


def _builtin(
    error_id: str,
    result: Mapping[str, Any],
    facts: Mapping[str, Any],
    what: str,
    reason: Optional[str] = None,
) -> Finding:
    error = BUILTIN_ERRORS[error_id]
    return Finding(
        error_id=error.id,
        title=error.title,
        why=error.why,
        fix=error.fix,
        facts=dict(facts),
        rule=str(result.get("rule_id")),
        target=result_entity(result),
        text=str(result.get("message") or ""),
        what=what,
        reason=reason,
    )


def _missing_entity(result: Mapping[str, Any]) -> Finding:
    """The reference entity of ``result``, which has no counterpart: its
    mapping name, kind and place in the reference. Paired with less than
    certainty (``_UNCERTAIN_MATCHES``), a not judged finding that names the
    best candidate (``candidate``) instead."""
    reference = (
        (result.get("locations") or {}).get("source") or result.get("source") or {}
    )
    entity_id = result.get("source_entity_id")
    if entity_id:
        name, kind = mapping_name(str(entity_id))
    else:
        name, kind = str(result_entity(result) or "?").replace(":", "."), None
    details = result.get("details") or {}
    status = details.get("match_status")
    facts = {
        "entity": name,
        "kind": kind,
        "file": reference.get("file"),
        "line": reference.get("line"),
        "match_status": status,
        "rules": [str(result.get("rule_id"))],
    }
    where = f"{facts['file'] or '?'}:{facts['line'] or '?'}"
    uncertain = _UNCERTAIN_MATCHES.get(str(status))
    if uncertain is not None:
        candidate_id = result.get("target_entity_id")
        candidate = mapping_name(str(candidate_id))[0] if candidate_id else None
        facts = {
            **{k: v for k, v in facts.items() if k != "rules"},
            "confidence": details.get("confidence"),
            "candidate": candidate,
            "rules": facts["rules"],
        }
        paired = f"`{candidate}`" if candidate else "nothing"
        return Finding(
            error_id=None,
            title=None,
            why=None,
            fix=None,
            facts={k: v for k, v in facts.items() if v is not None},
            rule=str(result.get("rule_id")),
            target=result_entity(result),
            text=str(result.get("message") or ""),
            what=(
                f"The tool could not pair `{name}` of the reference ({where}) with "
                f"certainty ({status}; best candidate {paired}); the checks on it "
                "did not run. Pair it with a mapping to judge it."
            ),
            reason=uncertain,
        )
    what = (
        f"The submission has no {kind or 'entity'} the tool could pair with `{name}` of "
        f"the reference ({where}); the checks on it could not run."
    )
    return _builtin(
        MISSING_REQUIRED_ENTITY,
        result,
        {k: v for k, v in facts.items() if v is not None},
        what,
    )


def _unresolved_names(result: Mapping[str, Any]) -> list[str]:
    """The names of a ``case_setup_failed`` result's cases that the
    submission could not resolve (``unresolved``, the case's ``$new``), first
    seen first."""
    details = result.get("details") or {}
    if result.get("status") != "FAILED" or details.get("reason") != _CASE_SETUP_FAILED:
        return []
    return list(
        dict.fromkeys(
            str(case["unresolved"])
            for case in details.get("cases") or []
            if isinstance(case, Mapping) and case.get("unresolved")
        )
    )


def _missing_case_entity(result: Mapping[str, Any], name: str) -> Finding:
    """A class the cases of ``result`` construct (``$new``) that the
    submission does not have: the reference has it, or the case could not
    run there either. ``required_by`` lists the entities whose cases need it."""
    module, _, qualname = name.rpartition(".")
    facts = {
        "entity": name,
        "rules": [str(result.get("rule_id"))],
        "required_by": [str(result_entity(result) or "?")],
    }
    what = (
        f"The submission has no `{name}`, which the cases of "
        f"`{facts['required_by'][0]}` construct; the checks that need it could not run."
    )
    finding = _builtin(MISSING_REQUIRED_ENTITY, result, facts, what)
    target = f"{module}:{qualname}" if module else qualname
    return Finding(**{**finding.__dict__, "target": target})


def _syntax_error(result: Mapping[str, Any]) -> Finding:
    """A file of the submission that does not parse: the file (relative to the
    submission's root), the line and the compiler's message."""
    details = result.get("details") or {}
    source = (result.get("locations") or {}).get("source") or result.get("source") or {}
    file = str(details.get("file") or source.get("file") or "?")
    line = details.get("lineno") or source.get("line")
    message = str(details.get("message") or details.get("exception") or "")
    facts = {
        "file": file,
        "line": line,
        "offset": details.get("offset"),
        "message": message,
    }
    what = f"File `{file}` does not parse: {message} (line {line or '?'})."
    return _builtin(
        SYNTAX_ERROR,
        result,
        {k: v for k, v in facts.items() if v is not None},
        what,
        reason=SYNTAX_ERROR,
    )


def _is_missing_entity(result: Mapping[str, Any]) -> bool:
    details = result.get("details") or {}
    return (
        result.get("status") == "FAILED"
        and details.get("reason") == _REQUIRED_TARGET_MISSING
    )


def _is_syntax_error(result: Mapping[str, Any]) -> bool:
    """A file of the submission does not parse. The reference's syntax error,
    which every target's results repeat, names no file of the submission
    (``details.file``): it is no verdict on the submission, but no finding of
    this kind either."""
    details = result.get("details") or {}
    return (
        str(result.get("rule_id")) == _SYNTAX_RULE
        and result.get("status") in VIOLATION_STATUSES
        and bool(details.get("file"))
    )


def _not_judged(result: Mapping[str, Any], text: str) -> Finding:
    return Finding(
        error_id=None,
        title=None,
        why=None,
        fix=None,
        facts={},
        rule=str(result.get("rule_id")),
        target=result_entity(result),
        text=text,
        reason=not_judged_reason(result),
    )


def classify_result(principle: Principle, result: Mapping[str, Any]) -> list[Finding]:
    """One finding per violation fact of a failed result, in the facts' order.

    A result whose status is no violation (``OK``, ``SKIPPED``, ``WARNING``)
    gives none; a reference entity without a counterpart one
    ``missing_required_entity`` finding (one paired with less than certainty
    a not judged one), a case that could not resolve its ``$new`` one per
    name, a file that does not parse one ``syntax_error`` finding; any other
    ``ERROR`` result, or a failed one without facts, one not judged finding
    with the result's message."""
    if result.get("status") not in VIOLATION_STATUSES:
        return []
    if _is_missing_entity(result):
        return [_missing_entity(result)]
    unresolved = _unresolved_names(result)
    if unresolved:
        return [_missing_case_entity(result, name) for name in unresolved]
    if _is_syntax_error(result):
        return [_syntax_error(result)]
    details = result.get("details") or {}
    message = str(result.get("message") or details.get("summary") or "")
    facts = list(details.get("facts") or [])
    if not facts or result.get("status") == "ERROR":
        return [_not_judged(result, message)]
    texts = list(details.get("violations") or [])
    if len(texts) != len(facts):
        texts = [message] * len(facts)
    rule = str(result.get("rule_id"))
    findings: list[Finding] = []
    for fact, text in zip(facts, texts):
        error = choose_error(principle, rule, fact)
        if error is None:
            findings.append(_unclassified(result, fact, str(text)))
            continue
        findings.append(
            Finding(
                error_id=error.id,
                title=error.title,
                why=error.why,
                fix=error.fix,
                facts=dict(fact),
                rule=rule,
                target=result_entity(result),
                text=str(text),
                what=fill_what(error.what, result, fact) if error.what else None,
            )
        )
    return findings


def _merged(finding: Finding) -> bool:
    """A finding about a reference entity, one per entity however many rules
    give it: a missing one, or one paired with less than certainty."""
    return finding.error_id == MISSING_REQUIRED_ENTITY or (
        finding.reason in _UNCERTAIN_MATCHES.values()
    )


def _noise(finding: Finding) -> bool:
    """What may follow from a file the tool could not read: an entity without
    a sure counterpart (it may be in that file) or a check that could not run
    (the file may be why)."""
    return finding.error_id != SYNTAX_ERROR and (
        finding.error_id == MISSING_REQUIRED_ENTITY or finding.not_judged
    )


def classify_target(
    principle: Principle, results: Iterable[Mapping[str, Any]]
) -> list[Finding]:
    """The findings of one submission's results, in the results' order.

    ``classify_result`` of each result, with one finding per reference entity
    (``missing_required_entity``, or not judged ``ambiguous_match`` or
    ``low_confidence_match``) whose ``facts.rules`` lists every rule that
    requires it (and ``facts.required_by`` every entity whose cases need it).
    When a file of the submission does not parse, its ``syntax_error``
    findings and the violations found in the code the tool could read (a
    catalogue error or unclassified), but none of what may follow from the
    unreadable file (``_noise``). A ``read`` that is the object of a method
    call (``receiver``) on the line a ``write`` of its attribute is on is
    part of that write and no finding of its own, and so is a
    ``missing_delegation`` of a method whose class builds a forbidden object
    (an ``instance``): it never calls the collaborator it was given because
    it built its own. One defect is one finding
    (``_defect``): a call through a helper by its caller and the line the
    detour starts at, another call, a read or a static fact by its place,
    another fact of a case by all but its case; ``facts.cases`` then lists
    the cases."""
    results = list(results)
    broken = any(_is_syntax_error(result) for result in results)
    findings: list[Finding] = []
    merged: dict[tuple[Optional[str], Optional[str], Any], Finding] = {}
    for result in results:
        for finding in classify_result(principle, result):
            if broken and _noise(finding):
                continue
            if not _merged(finding):
                findings.append(finding)
                continue
            key = (finding.error_id, finding.reason, finding.facts["entity"])
            first = merged.get(key)
            if first is None:
                merged[key] = finding
                findings.append(finding)
                continue
            for name in ("rules", "required_by"):
                for item in finding.facts.get(name) or []:
                    # The first may lack the fact (a missing entity has no
                    # required_by; a case that cannot set it up has).
                    # (Every finding's facts are built as a dict.)
                    have = cast(dict, first.facts).setdefault(name, [])
                    if item not in have:
                        have.append(item)
    return _collapsed(
        _without_delegations_of_builders(_without_reads_of_writes(findings))
    )


# Facts of one place in the code: the same kind at the same place is one
# defect however many cases or rules report it.
_PLACE_KINDS = ("call", "read", "not_subclass", "not_abstract")


def _defect(finding: Finding) -> Optional[tuple[Any, ...]]:
    """What makes two findings one defect, or ``None`` when nothing does: a
    call reached through other code (``via``) by its error, caller and the
    caller's line the detour starts at (two callers of one printing helper
    are two defects); a call, read or static fact by its error and place
    (file, line, and the attribute or callee); any other fact of a case by
    its error, rule and every key but ``case``."""
    facts = dict(finding.facts or {})
    if finding.not_judged or not facts.get("kind"):
        return None
    if facts["kind"] == "call" and facts.get("via"):
        return (
            finding.error_id,
            "via",
            facts.get("caller"),
            facts.get("origin_line"),
            facts.get("callee"),
        )
    if facts["kind"] in _PLACE_KINDS:
        return (
            finding.error_id,
            facts["kind"],
            facts.get("file"),
            facts.get("line"),
            facts.get("attribute"),
            facts.get("callee"),
        )
    if "case" not in facts:
        return None
    facts.pop("case")
    return (
        finding.error_id,
        finding.rule,
        json.dumps(facts, sort_keys=True, default=str),
    )


def _collapsed(findings: list[Finding]) -> list[Finding]:
    """One finding per defect (``_defect``), the first; its facts list the
    ``cases`` of every finding it stands for (when they have cases)."""
    first: dict[tuple[Any, ...], int] = {}
    cases: dict[int, list[Any]] = {}
    kept: list[Finding] = []
    for finding in findings:
        key = _defect(finding)
        if key is None:
            kept.append(finding)
            continue
        case = (finding.facts or {}).get("case")
        if key not in first:
            first[key] = len(kept)
            kept.append(finding)
            cases[first[key]] = []
        at = first[key]
        if case is not None and case not in cases[at]:
            cases[at].append(case)
    return [
        (
            replace(finding, facts={**finding.facts, "cases": cases[index]})
            if len(cases.get(index) or []) > 1
            else finding
        )
        for index, finding in enumerate(kept)
    ]


def _place(finding: Finding) -> tuple[Any, Any, Any]:
    facts = finding.facts or {}
    return (facts.get("file"), facts.get("line"), facts.get("attribute"))


def _without_reads_of_writes(findings: list[Finding]) -> list[Finding]:
    """``findings`` without a ``read`` that is the object a method is called
    on (``receiver``) at the place (file, line, attribute) of a ``write`` of
    the change the receiver makes: ``obj._x.append(v)`` reads ``_x`` to
    change its contents (``receiver`` ``mutated``), which is one defect, the
    ``mutated`` write; ``obj._x = {... obj._x ...}`` rebuilds it
    (``assigned``). Any other read stays: ``a._x = b._x`` reads another
    object, and so does ``a._x = b._x.setdefault(k, d)``, whose ``assigned``
    write is a's. A receiver given as ``True`` folds into any write there."""
    written: set[tuple[Any, ...]] = set()
    for f in findings:
        facts = f.facts or {}
        if facts.get("kind") == "write":
            written.add(_place(f))
            written.add((*_place(f), facts.get("change")))

    def folded(f: Finding) -> bool:
        facts = f.facts or {}
        receiver = facts.get("receiver")
        if facts.get("kind") != "read" or not receiver:
            return False
        if receiver is True:
            return _place(f) in written
        return (*_place(f), receiver) in written

    return [f for f in findings if not folded(f)]


def _owner(code: Any) -> Optional[str]:
    """``module:Class`` of a method given as ``module:Class.method``."""
    module, _, qualname = str(code or "").partition(":")
    owner = qualname.rpartition(".")[0]
    return f"{module}:{owner}" if module and owner else None


def _without_delegations_of_builders(findings: list[Finding]) -> list[Finding]:
    """``findings`` without a ``missing_delegation`` of a method whose class
    builds an object the task forbids building (an ``instance`` fact created
    by code of the same class): a constructor that builds its own
    collaborator never calls the one it was given, which is one defect, the
    building. Likewise without one of a method that tests the kind of the
    object it was given (``type_switch_on_strategy``)."""
    builders = {
        _owner((f.facts or {}).get("creator"))
        for f in findings
        if (f.facts or {}).get("kind") == "instance" and f.error_id is not None
    } - {None}
    # A method that asks which kind of object it was given (a classified
    # isinstance/type call) and computes the kinds it tests by itself never
    # delegates for them either: one defect, the test of the kind.
    switchers = {
        (f.facts or {}).get("caller")
        for f in findings
        if (f.facts or {}).get("kind") == "call"
        and (f.facts or {}).get("callee") in _TYPE_CALLEES
        and f.error_id is not None
    } - {None}
    return [
        f
        for f in findings
        if not (
            (f.facts or {}).get("kind") == "missing_delegation"
            and (
                _owner((f.facts or {}).get("caller")) in builders
                or (f.facts or {}).get("caller") in switchers
            )
        )
    ]


_TYPE_CALLEES = frozenset({"builtins:isinstance", "builtins:type"})
