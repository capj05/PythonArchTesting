"""The verdict of one principle for one submission (design § 5.5).

``judge_principle`` runs the self-task (``selftask``) over a copy of the
submission with ``run_evaluation``. A finding of a typical error is proof
in itself: the principle is ``violated`` and no mutant runs, since the core
would only report the error as ``reference_fails``. A finding without a
verdict (a case that timed out, a file that does not parse) already keeps
the principle from being ``ok``, and every mutant would run into it again (a
game loop no case ends costs the whole timeout per mutant), so no mutant runs
then either (``mutation:not_run``). Without either, ``prepare_task`` checks
that the cases cover the bound entities and that a mutant of every typical
error is caught; that alone lets the principle be ``ok``.

``decide_status`` turns the evidence into the status, in this order:

1. the discovery says the principle does not apply: ``not_applied``;
2. a finding of a typical error (``error_id`` set, judged): ``violated``,
   except a missing call into a module (``missing_call`` of
   ``require_runtime_calls``, ``logic_in_main``), which is never
   ``violated`` in global mode: whether the io should call the logic depends
   wholly on which entities discovery took for io and logic, so the finding
   is unverified, with the most specific reason that applies:

   - ``missing_call_in_some_cases`` (with the entity, the ``module``, the
     ``cases`` that missed it and ``case_count``): another case of the
     entity did call the module (an AI's case that quits at once calls no
     logic); the number of cases comes from the result of the check;
   - ``missing_call_role_disputed`` (with the entity and the ``module``):
     discovery disputed the io entity as an action that may read the
     keyboard; an input helper calls no logic by design, and an action is
     no io;
   - ``missing_call_self_calls_unobserved`` (with the entity, the
     ``module`` and the ``logic`` methods): the io method's class family
     (the class, its project bases and subclasses) holds a bound ``logic``
     method, reached by ``self.m(...)``, which the run does not record;
   - ``missing_call_role_dependent`` (with the entity and the ``module``):
     any other missing call.

   No mutant runs then either: the
   unchanged submission fails that check, so its mutants could not count;
3. a finding without a verdict (a syntax error, a case that could not be
   set up) is unverified with its reason;
4. a check whose cases are not accepted, cover less than ``min_coverage`` or
   report no coverage at all is unverified (``coverage``);
5. a typical error whose mutation check is not ``killed``,
   ``not_applicable`` or ``gap`` (``survived``, ``not_run``, ``no_mutants``,
   ``killed_other``, ``not_verifiable_by_mutation``, ``reference_fails``) is
   unverified (``mutation:<status>``), and so is a run that did not check
   every mutant (``mutation:truncated``) or none at all
   (``mutation:not_run``); a problem of the task is unverified (``task``);
6. an entity left out of the task for lack of cases is unverified
   (``no cases``);
7. a bound entity whose role is disputed (by the AI, or by discovery: an
   action that reads the keyboard, possibly ``input_in_logic``) keeps a
   principle that is not violated from being ``ok`` (``role_disputed``,
   with the entity, its role and the doubt as ``why``): the teacher
   decides; a violated principle stays violated;
8. ``ok`` when nothing is unverified, else ``unverified``.

A finding no typical error explains (``error_id`` ``None``, judged) never
makes the principle ``violated``: it is listed under ``unclassified`` for the
teacher. The target is a copy of the reference, so the check that found it
fails on the reference too. That "<marker> fails on the reference" problem
is explained by the unclassified findings and is never an unverified reason
of its own; the status follows the statuses of the errors alone. An error of
that check which is not ``killed``, ``not_applicable`` or ``gap`` (typically
``reference_fails``, since no mutant counts on a check the reference fails)
is unverified and names the cause (``because``: ``unclassified findings``,
``entities``: where they are, ``why``: the problem when there is one). When
every error of that check is ``not_applicable`` or ``gap``, the principle can
be ``ok`` with the unclassified findings listed.

A finding on an entity whose role the AI disputed keeps its status and is
flagged ``role_disputed``: the teacher decides. A finding belongs to a
disputed entity when its own entity is, or lies inside, the disputed one,
or when the object it writes or reads is of the disputed class (an
encapsulation owner: the finding's entity is then the client that wrote).

The entity of a finding is its ``facts["entity"]`` when the core names one (a
missing entity), else its target, ``actions:status`` written as the roles
write it, ``actions.status``.

A task the core refuses (a role every entity of which was dropped for lack of
cases leaves the role unbound) runs nothing: the principle is ``unverified``
with each problem (``task``) and the dropped entities.

``unexercised`` lists the lines of each checked entity that no case ran, as
the run's coverage reports them, for every status: a line no case ran is
checked by nothing, and an ``ok`` must not hide it.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.entities import Entity
from pythonarchtesting.global_mode.model import (
    PrincipleOutcome,
    RoleDiscovery,
    Status,
)
from pythonarchtesting.global_mode.selftask import SelfTask
from pythonarchtesting.global_mode.source import Scan, entities_of, scan
from pythonarchtesting.principles import (
    Finding,
    Principle,
    principle_markers,
    result_entity,
    rule_marker,
)

# The mutation statuses that let a principle be ok (design § 5.5).
_MUTATION_OK = frozenset({"killed", "not_applicable", "gap"})
MISSING_CALL_IN_SOME_CASES = "missing_call_in_some_cases"
SELF_CALLS_UNOBSERVED = "missing_call_self_calls_unobserved"
MISSING_CALL_ROLE_DISPUTED = "missing_call_role_disputed"
MISSING_CALL_ROLE_DEPENDENT = "missing_call_role_dependent"
_REQUIRE_CALLS = "require_runtime_calls"
# How load_task words a role no entity is bound to (``task.load_task``).
_UNBOUND = re.compile(
    r"^role '(?P<role>[^']+)' is not bound: the checks of '(?P<principle>[^']+)' "
    r"need it \((?P<markers>[^)]*)\); add [^ ]+ = \[\.\.\.\] to \[roles\]$"
)

_WARNING = "WARNING:"
# How prepare_task words a check the unchanged reference fails
# (``tasks._reference_problems``): "<marker> fails on the reference: <why>".
_FAILS_ON_REFERENCE = " fails on the reference"


def _min_coverage(value: Optional[float]) -> float:
    """``value``, else the core's default threshold (imported here, so that
    the package does not load the MCP layer when it is imported)."""
    if value is not None:
        return value
    from pythonarchtesting.mcp_server.authoring import DEFAULT_MIN_COVERAGE

    return DEFAULT_MIN_COVERAGE


def _entity(finding: Finding) -> Optional[str]:
    """The entity of ``finding`` as the roles name it (module docstring)."""
    named = finding.facts.get("entity") if finding.facts else None
    if named:
        return str(named)
    if finding.target is None:
        return None
    return finding.target.replace(":", ".")


def _classified(finding: Finding) -> bool:
    return finding.error_id is not None and not finding.not_judged


def _unclassified(finding: Finding) -> bool:
    return finding.error_id is None and not finding.not_judged


def _within(name: str, bound: str) -> bool:
    return name == bound or name.startswith(bound + ".")


def _of_class(cls: str, bound: str) -> bool:
    """Whether the class a fact names is the bound entity ``bound``. An
    instance fact names it ``module:Class``; a write or read fact only by its
    qualified name (``Cargo``), which matches a bound class of that name in
    any module."""
    if ":" in cls:
        module, _, qualname = cls.partition(":")
        return bound == (f"{module}.{qualname}" if module else qualname)
    return bound == cls or bound.endswith("." + cls)


def _disputed(discovery: RoleDiscovery, finding: Finding) -> Optional[str]:
    """The AI's doubt about the bound entity ``finding`` belongs to (module
    docstring), else ``None``."""
    entity = _entity(finding)
    cls = finding.facts.get("class") if finding.facts else None
    for bound in discovery.roles.values():
        for candidate in bound:
            if candidate.disputed is None:
                continue
            if entity is not None and _within(entity, candidate.entity):
                return candidate.disputed
            if cls and _of_class(str(cls), candidate.entity):
                return candidate.disputed
    return None


def _missed_cases(finding: Finding) -> set[Any]:
    """The cases a finding of a case fact stands for (``case`` or the merged
    ``cases``)."""
    facts = finding.facts or {}
    cases = list(facts.get("cases") or [])
    if facts.get("case") is not None:
        cases.append(facts["case"])
    return set(cases)


def _missing_call(finding: Finding) -> bool:
    return _classified(finding) and (finding.facts or {}).get("kind") == "missing_call"


def relax_missing_calls(
    findings: Sequence[Finding], counts: Mapping[str, int]
) -> list[Finding]:
    """``findings`` with each missing call into a module that some case of
    the entity did make turned into a finding without a verdict
    (``missing_call_in_some_cases``; module docstring). ``counts`` is the
    number of cases per entity (``cases_per_entity``); an entity it does not
    name keeps its finding. Idempotent."""
    missed: dict[tuple[Optional[str], str], set[Any]] = {}
    for finding in findings:
        if _missing_call(finding):
            key = (_entity(finding), str(finding.facts.get("module")))
            missed.setdefault(key, set()).update(_missed_cases(finding))
    relaxed: list[Finding] = []
    for finding in findings:
        if _missing_call(finding):
            entity = _entity(finding)
            cases = missed[(entity, str(finding.facts.get("module")))]
            count = counts.get(entity) if entity is not None else None
            if count is not None and cases and len(cases) < count:
                finding = replace(
                    finding,
                    reason=MISSING_CALL_IN_SOME_CASES,
                    facts={
                        **finding.facts,
                        "cases": sorted(cases, key=str),
                        "case_count": count,
                    },
                )
        relaxed.append(finding)
    return relaxed


def _class_of(name: str, families: Mapping[str, Collection[str]]) -> Optional[str]:
    """The class a method ``name`` (``game.Game.run``) belongs to, when it is
    a class of the project, else ``None``."""
    owner = name.rsplit(".", 1)[0] if "." in name else None
    return owner if owner in families else None


def relax_self_calls(
    findings: Sequence[Finding],
    discovery: RoleDiscovery,
    families: Mapping[str, Collection[str]],
) -> list[Finding]:
    """``findings`` with each missing call (``missing_call``) of an ``io``
    method whose class family (``families``: class -> the class, its
    project bases and subclasses) holds a bound ``logic`` method turned into
    a finding without a verdict (``missing_call_self_calls_unobserved``,
    with the ``logic`` methods): such an io method reaches its logic by
    ``self.m(...)``, which the run does not record (module docstring).
    Idempotent."""
    io = {b.entity for b in discovery.roles.get("io", ())}
    logic = [b.entity for b in discovery.roles.get("logic", ())]
    relaxed: list[Finding] = []
    for finding in findings:
        entity = _entity(finding)
        cls = (
            _class_of(entity, families) if entity is not None and entity in io else None
        )
        if _missing_call(finding) and cls is not None:
            family = families[cls]
            reached = [m for m in logic if _class_of(m, families) in family]
            if reached:
                finding = replace(
                    finding,
                    reason=SELF_CALLS_UNOBSERVED,
                    facts={**finding.facts, "logic": reached},
                )
        relaxed.append(finding)
    return relaxed


def relax_disputed_calls(
    findings: Sequence[Finding], discovery: RoleDiscovery
) -> list[Finding]:
    """``findings`` with each missing call (``missing_call``) of an ``io``
    entity that discovery disputed as a possible action reading the
    keyboard (``POSSIBLY_INPUT_IN_LOGIC``) turned into a finding without a
    verdict (``missing_call_role_disputed``): an input helper calls no logic
    by design, and an action is no io, so the missing call is evidence of
    neither (module docstring). Idempotent."""
    from pythonarchtesting.global_mode.discovery.io_separation import (
        POSSIBLY_INPUT_IN_LOGIC,
    )

    disputed = {
        b.entity
        for b in discovery.roles.get("io", ())
        if b.disputed == POSSIBLY_INPUT_IN_LOGIC
    }
    return [
        (
            replace(finding, reason=MISSING_CALL_ROLE_DISPUTED)
            if _missing_call(finding) and _entity(finding) in disputed
            else finding
        )
        for finding in findings
    ]


def _relax(
    findings: Sequence[Finding],
    discovery: RoleDiscovery,
    counts: Mapping[str, int],
    families: Mapping[str, Collection[str]],
) -> list[Finding]:
    """Every missing call without a verdict, with the most specific reason
    that applies (module docstring, rule 2)."""
    relaxed = relax_self_calls(
        relax_disputed_calls(relax_missing_calls(findings, counts), discovery),
        discovery,
        families,
    )
    return relax_role_dependent(relaxed)


def relax_role_dependent(findings: Sequence[Finding]) -> list[Finding]:
    """``findings`` with each missing call (``missing_call``) still judged
    turned into a finding without a verdict (``missing_call_role_dependent``):
    whether the io should call the logic depends wholly on which entities
    discovery took for io and logic, so a missing call is never proof in
    global mode (module docstring). Idempotent."""
    return [
        (
            replace(finding, reason=MISSING_CALL_ROLE_DEPENDENT)
            if _missing_call(finding)
            else finding
        )
        for finding in findings
    ]


def _not_judged_entry(finding: Finding) -> dict[str, Any]:
    entry: dict[str, Any] = {"entity": _entity(finding), "reason": finding.reason}
    if finding.reason == MISSING_CALL_IN_SOME_CASES:
        facts = finding.facts
        entry.update(
            error=finding.error_id,
            module=facts.get("module"),
            cases=list(facts.get("cases") or []),
            case_count=facts.get("case_count"),
        )
    elif finding.reason in (MISSING_CALL_ROLE_DISPUTED, MISSING_CALL_ROLE_DEPENDENT):
        entry.update(error=finding.error_id, module=finding.facts.get("module"))
    elif finding.reason == SELF_CALLS_UNOBSERVED:
        facts = finding.facts
        entry.update(
            error=finding.error_id,
            module=facts.get("module"),
            logic=list(facts.get("logic") or []),
        )
    return entry


def split_findings(
    discovery: RoleDiscovery, findings: Sequence[Finding]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The findings of typical errors, each flagged ``role_disputed`` when
    its entity's role is disputed, and the unclassified ones; findings
    without a verdict are neither (``decide_status`` lists them)."""
    classified: list[dict[str, Any]] = []
    for finding in findings:
        if not _classified(finding):
            continue
        data = finding.to_dict()
        why = _disputed(discovery, finding)
        if why is not None:
            data["role_disputed"] = why
        classified.append(data)
    unclassified = [f.to_dict() for f in findings if _unclassified(f)]
    return classified, unclassified


def _coverage_gaps(
    prepared: Mapping[str, Any], min_coverage: float
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for check in prepared.get("checks") or []:
        if check.get("status") == "not_applicable":
            continue  # nothing to run: the check has nothing to check
        coverage = check.get("coverage")
        low = coverage is None or coverage < min_coverage
        if check.get("accepted") is False or low:
            gap: dict[str, Any] = {"entity": check["entity"], "reason": "coverage"}
            if coverage is not None:
                gap["coverage"] = coverage
            if check.get("reasons"):
                gap["why"] = "; ".join(str(r) for r in check["reasons"])
            gaps.append(gap)
    return gaps


def _blamed(findings: Sequence[Finding]) -> dict[str, list[str]]:
    """The entities of the unclassified findings, by the marker of the check
    that found them."""
    blamed: dict[str, list[str]] = {}
    for finding in findings:
        if _unclassified(finding):
            entities = blamed.setdefault(rule_marker(finding.rule), [])
            entity = _entity(finding)
            if entity is not None and entity not in entities:
                entities.append(entity)
    return blamed


def _mutation_gaps(
    prepared: Optional[Mapping[str, Any]], blamed: Mapping[str, list[str]]
) -> list[dict[str, Any]]:
    """Why mutation does not verify the principle. A "<marker> fails on the
    reference" problem of a marker with unclassified findings (``blamed``)
    is explained by them and is never listed on its own; each unverified
    error of that marker names them (``because``, ``entities``, and the
    problem as ``why``)."""
    if prepared is None:
        return [{"reason": "mutation:not_run"}]
    gaps: list[dict[str, Any]] = []
    folded: dict[str, str] = {}
    for problem in (str(p) for p in prepared.get("problems") or []):
        if problem.startswith(_WARNING):
            continue
        marker = next(
            (m for m in blamed if problem.startswith(f"{m}{_FAILS_ON_REFERENCE}")),
            None,
        )
        if marker is not None:
            folded[marker] = problem
        else:
            gaps.append({"reason": "task", "why": problem})
    for error in prepared.get("errors") or []:
        status = error["status"]
        if status in _MUTATION_OK:
            continue
        gap: dict[str, Any] = {"error": error["error"], "reason": f"mutation:{status}"}
        marker = str(error.get("detected_by"))
        if marker in blamed:
            gap["because"] = "unclassified findings"
            gap["entities"] = list(blamed[marker])
            if marker in folded:
                gap["why"] = folded[marker]
        gaps.append(gap)
    if prepared.get("truncated"):
        gaps.append({"reason": "mutation:truncated"})
    return gaps


def decide_status(
    discovery: RoleDiscovery,
    findings: Sequence[Finding],
    prepared: Mapping[str, Any] | None,
    dropped: Sequence[dict[str, Any]],
    *,
    min_coverage: Optional[float] = None,
    case_counts: Optional[Mapping[str, int]] = None,
    class_families: Optional[Mapping[str, Collection[str]]] = None,
) -> tuple[Status, list[dict[str, Any]]]:
    """The status of the principle and why parts of it are unverified
    (module docstring). ``prepared`` is ``prepare_task``'s result, ``None``
    when it did not run (a violated principle runs no mutant);
    ``case_counts`` the number of cases per entity of the
    ``require_runtime_calls`` results (``cases_per_entity``), which tells a
    missing call of every case from one of some; ``class_families`` the
    family of each project class (``families_of_classes``), which tells an io
    method that reaches its logic by ``self.m(...)``. ``min_coverage``
    defaults to the core's threshold."""
    if discovery.not_applied is not None:
        return "not_applied", []
    return _status(
        discovery,
        _relax(findings, discovery, case_counts or {}, class_families or {}),
        prepared,
        dropped,
        min_coverage,
    )


def _status(
    discovery: RoleDiscovery,
    findings: Sequence[Finding],
    prepared: Mapping[str, Any] | None,
    dropped: Sequence[dict[str, Any]],
    min_coverage: Optional[float],
) -> tuple[Status, list[dict[str, Any]]]:
    """``decide_status`` of findings already relaxed (``_relax``)."""
    if discovery.not_applied is not None:
        return "not_applied", []
    violated = any(_classified(f) for f in findings)
    unverified: list[dict[str, Any]] = []
    for finding in findings:
        if (
            finding.not_judged
            and (entry := _not_judged_entry(finding)) not in unverified
        ):
            unverified.append(entry)
    if prepared is not None:
        unverified.extend(_coverage_gaps(prepared, _min_coverage(min_coverage)))
    if not violated:
        unverified.extend(_mutation_gaps(prepared, _blamed(findings)))
    unverified.extend(dict(d) for d in dropped)
    if violated:
        return "violated", unverified
    unverified.extend(
        {
            "entity": b.entity,
            "role": role,
            "reason": "role_disputed",
            "why": b.disputed,
        }
        for role, bound in discovery.roles.items()
        for b in bound
        if b.disputed is not None
    )
    return ("unverified" if unverified else "ok"), unverified


def _copy(submission: Path, work_dir: Path) -> Path:
    """A fresh copy of the submission to evaluate, ``work_dir/target/<name>``."""
    copy = work_dir / "target" / submission.name
    if copy.exists():
        shutil.rmtree(copy)
    # As prepare_task copies a reference: a symlink stays a link (a loop
    # ``loop -> .`` would recurse without end), and ``.git``, ``.venv`` and
    # caches are no part of the program.
    shutil.copytree(
        submission,
        copy,
        symlinks=True,
        ignore=shutil.ignore_patterns("__pycache__", ".*"),
    )
    return copy


def _sites(principle: Principle, target: Mapping[str, Any]) -> int:
    """The bound entities with a check: the distinct entities of the
    results of the principle's checks."""
    markers = principle_markers(principle)
    return len(
        {
            result_entity(r)
            for r in target["results"]
            if rule_marker(str(r["rule_id"])) in markers
        }
        - {None}
    )


def cases_per_entity(target: Mapping[str, Any]) -> dict[str, int]:
    """Per entity the number of cases its ``require_runtime_calls`` result
    ran (``details.case_count``), from one target of a run's report."""
    counts: dict[str, int] = {}
    for result in target.get("results") or []:
        if rule_marker(str(result.get("rule_id"))) != _REQUIRE_CALLS:
            continue
        entity = result_entity(result)
        count = (result.get("details") or {}).get("case_count")
        if entity is not None and isinstance(count, int):
            counts[entity.replace(":", ".")] = count
    return counts


def unexercised_lines(
    principle: Principle, target: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Per entity a check of the principle ran, the lines of it no case ran
    (``entity``, ``file``, ``lines``), as the run's coverage reports them
    (``details.coverage.unexercised_lines``); entities whose every line ran
    are left out. By entity name."""
    markers = principle_markers(principle)
    found: dict[str, dict[str, Any]] = {}
    for result in target.get("results") or []:
        if rule_marker(str(result.get("rule_id"))) not in markers:
            continue
        coverage = (result.get("details") or {}).get("coverage")
        entity = result_entity(result)
        if not isinstance(coverage, Mapping) or entity is None:
            continue
        lines = [int(line) for line in coverage.get("unexercised_lines") or []]
        if not lines:
            continue
        name = entity.replace(":", ".")
        entry = found.setdefault(
            name, {"entity": name, "file": coverage.get("file"), "lines": []}
        )
        entry["lines"] = sorted(set(entry["lines"]) | set(lines))
    return [found[name] for name in sorted(found)]


def _global_problem(problem: str) -> str:
    """A problem of ``load_task`` in the words of global mode: the teacher
    writes no roles there, so "add <role> = [...] to [roles]" would be no
    advice. A role no entity is bound to means discovery found none or the AI
    wrote cases for none."""
    match = _UNBOUND.match(problem)
    if match is None:
        return problem
    role, principle = match["role"], match["principle"]
    return (
        f"no {role} was found, or every {role} found lacks cases: the checks of "
        f"{principle!r} that need it ({match['markers']}) cannot run, so the task "
        "was not run and none of its checks ran, the static ones included"
    )


def _task_problems(
    task_dir: Path, config: Optional[str], scanned: Optional[Scan] = None
) -> list[str]:
    """What keeps the core from running the task at ``task_dir``: the
    problems ``load_task`` and ``bind_task`` raise, as ``prepare_task``
    finds them (``tasks._bind``), in the words of global mode
    (``_global_problem``); empty when it can run. ``scanned`` is the
    submission as the caller read it (``source.entities_of``)."""
    from pythonarchtesting.mcp_server.evaluation import resolve_config
    from pythonarchtesting.principles.task import TaskError, bind_task, load_task

    try:
        task = load_task(task_dir)
        loaded, applied = resolve_config(task_dir, config)
        bind_task(task, entities_of(task.reference, loaded, applied, scanned))
    except TaskError as error:
        return [_global_problem(str(p)) for p in error.problems]
    return []


def _refused(
    discovery: RoleDiscovery, task: SelfTask, problems: Sequence[str]
) -> PrincipleOutcome:
    """The outcome of a task the core refuses: nothing ran."""
    _, unverified = decide_status(
        discovery,
        [],
        {"accepted": False, "problems": list(problems), "checks": [], "errors": []},
        task.dropped,
    )
    return PrincipleOutcome(
        principle=discovery.principle,
        status="unverified",
        roles=discovery.roles,
        findings=(),
        unverified=tuple(unverified),
        coverage=None,
        mutation=None,
        sites=0,
        violations=0,
    )


def families_of_classes(entities: Sequence[Entity]) -> dict[str, frozenset[str]]:
    """The family of each class of the project (not of its tests), by
    name: the class, its project bases and its project subclasses."""
    from pythonarchtesting.global_mode.discovery._ast import (
        class_family,
        classes,
        name_of,
        project_entities,
    )

    project = project_entities(entities)
    family = class_family(project)
    return {name_of(e): frozenset(family(name_of(e))) for e, _ in classes(project)}


def _unchanged(states: Sequence[Any], copy: Path) -> Optional[list[Any]]:
    """The results of the run over ``copy`` (the unchanged submission), or
    ``None`` when the run has no state of it."""
    for state in states:
        if Path(state.target_path).resolve() == copy.resolve():
            return list(state.rule_results)
    return None


def judge_principle(
    submission: Path,
    discovery: RoleDiscovery,
    task: SelfTask,
    work_dir: Path,
    *,
    min_coverage: Optional[float] = None,
    sandbox: str | None = None,
    config: str | None = None,
    scanned: Optional[Scan] = None,
) -> PrincipleOutcome:
    """Judge ``discovery.principle`` in ``submission`` by its self-task
    (module docstring). A principle that does not apply, or whose task the
    core refuses, runs nothing; else the run writes under ``work_dir``
    (``target/`` the copy, ``out/`` the report). ``coverage`` is the lowest
    coverage of a checked entity's cases, ``None`` when ``prepare_task`` did
    not run; ``min_coverage`` defaults to the core's threshold. ``scanned``
    is the submission as the caller read it (``source.scan``), read from
    ``submission`` when not given. The unchanged submission runs once by the
    task's checks: ``prepare_task`` takes those results as its mutation
    baseline instead of running it again."""
    from pythonarchtesting.mcp_server.evaluation import run_evaluation
    from pythonarchtesting.mcp_server.reports import _findings, load_report
    from pythonarchtesting.mcp_server.tasks import prepare_task
    from pythonarchtesting.principles.catalog import get_principle

    if discovery.not_applied is not None:
        return PrincipleOutcome(
            principle=discovery.principle,
            status="not_applied",
            roles=discovery.roles,
            findings=(),
            unverified=(),
            coverage=None,
            mutation=None,
            sites=0,
            violations=0,
        )
    min_coverage = _min_coverage(min_coverage)
    principle = get_principle(discovery.principle)
    task_dir = Path(task.task_dir).resolve()
    problems = _task_problems(task_dir, config, scanned)
    if problems:
        return _refused(discovery, task, problems)
    work_dir = Path(work_dir).resolve()
    copy = _copy(Path(submission).resolve(), work_dir)
    states: list[Any] = []
    run = run_evaluation(
        str(task_dir),
        str(work_dir / "out"),
        targets=[str(copy)],
        dynamic=True,
        sandbox=sandbox,
        config=config,
        states=states,
    )
    target = load_report(run["report_json"])["targets"][0]
    counts = cases_per_entity(target)
    if scanned is None:
        scanned = scan(Path(submission), config)
    families = families_of_classes(scanned.entities)
    findings = _relax(_findings(principle, target), discovery, counts, families)
    prepared: Optional[dict[str, Any]] = None
    if not any(_classified(f) or f.not_judged for f in findings):
        prepared = prepare_task(
            str(task_dir),
            min_coverage=min_coverage,
            sandbox=sandbox,
            config=config,
            scanned=scanned,
            baseline=_unchanged(states, copy),
        )
    status, unverified = _status(
        discovery, findings, prepared, task.dropped, min_coverage
    )
    classified, unclassified = split_findings(discovery, findings)
    coverages = [
        float(c["coverage"])
        for c in (prepared or {}).get("checks", [])
        if c.get("coverage") is not None
    ]
    return PrincipleOutcome(
        principle=discovery.principle,
        status=status,
        roles=discovery.roles,
        findings=tuple(classified),
        unverified=tuple(unverified),
        coverage=min(coverages) if coverages else None,
        mutation=(
            {str(e["error"]): str(e["status"]) for e in prepared["errors"]}
            if prepared is not None
            else None
        ),
        sites=_sites(principle, target),
        violations=len({_entity(f) for f in findings if _classified(f)}),
        unclassified=tuple(unclassified),
        unexercised=tuple(unexercised_lines(principle, target)),
    )


__all__ = [
    "MISSING_CALL_IN_SOME_CASES",
    "MISSING_CALL_ROLE_DEPENDENT",
    "MISSING_CALL_ROLE_DISPUTED",
    "SELF_CALLS_UNOBSERVED",
    "cases_per_entity",
    "families_of_classes",
    "decide_status",
    "judge_principle",
    "relax_disputed_calls",
    "relax_missing_calls",
    "relax_role_dependent",
    "relax_self_calls",
    "split_findings",
    "unexercised_lines",
]
