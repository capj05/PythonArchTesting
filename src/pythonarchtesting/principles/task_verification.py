"""Verify a task an AI client wrote for a principle (``verify_task``).

A task (``principles.task``) is ``task.toml`` next to an unannotated
reference: the principle, its roles bound to entities, and the cases of each
entity. ``verify_task`` answers, deterministically, whether the task is ready
to grade a class:

1. ``task.toml`` is valid and fits the reference (``problems``); nothing else
   runs while it is not;
2. every generated check's cases run on the reference and cover it
   (``checks``, judged as ``check_cases`` judges them);
3. every typical error of the principle that names a mutation ``operator`` is
   caught: the operator seeds that kind of error into copies of the
   reference, in the entities of the check that detects it, and the check
   must fail on every copy and pass on the unchanged reference (``errors``;
   each check the reference fails is listed under ``problems`` with its
   message, since a static check runs no cases that could say why).
   ``killed`` counts the mutants whose failure is classified as that error
   (its signature matched); a mutant the check catches as another error is
   ``killed_other``. An error is ``killed`` (accepted) only with at least one
   signature-matched kill; when every kill is another error's, its status is
   ``killed_other``.
   The unchanged reference runs every check of the task, also when no
   operator finds anything to change; a check it fails (or that does not run
   on it) keeps the task from being accepted (``reference_passes: false``),
   and a mutant never counts as killed by such a check: the errors it
   detects are ``reference_fails``.
   An error without an operator, or whose operator cannot seed the call its
   signature names, is ``not_verifiable_by_mutation``; an error whose
   operator finds nothing to change anywhere in the reference (no public
   container to fill, no call into another module) is ``not_applicable``,
   with ``why``, and so is an error whose check has nothing to check in the
   task (``forbid_runtime_instantiation`` when its ``target_role`` binds no
   class; the check is listed as ``not_applicable`` too); a known gap is
   ``gap``. None of these keeps the task from
   being accepted. An operator that finds something to change, but nothing in
   the entities of the check, gives ``no_mutants``, which does: the task
   binds the role to other code than the one the error lives in. A file of
   the reference the operators cannot read gets no mutant: the ``why`` of a
   ``not_applicable`` or ``no_mutants`` error names it. More
   mutants than ``max_mutants`` are taken in turn from each error
   (``truncated: true``, which keeps the task from being accepted); an error
   left with none of its mutants is ``truncated``, with ``why``.

Nothing is written into the task: the mutants live in a temporary directory.
Which mutants seed which error is ``principles.task_mutants``'; whether one
was caught is ``verification.mutant_runs``'. A config path that cannot be
used, or a file of the task that is not UTF-8, raises ``InvalidInputError``;
a config or file problem is raised as it is.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.invalid_input import InvalidInputError
from pythonarchtesting.principles.task_mutants import (
    aimed_entities,
    detector_modules,
    missing_site,
    mutants_for,
    named_callees,
    parameter_classes,
    seed_candidates,
    spied,
    unread_files_note,
    unseedable_reason,
    untargeted_reason,
)
from pythonarchtesting.runner.settings import resolve_config
from pythonarchtesting.verification.cases import judge_cases
from pythonarchtesting.verification.mutant_runs import (
    copy_reference,
    did_not_run,
    in_turn,
    mutant_outcome,
    write_mutants,
)

_SURVIVORS_SHOWN = 3


def _problems(state: Any) -> list[str]:
    """What the compiler refused or warned about among the task's declarations
    (a ``compiler_invalid_param`` is a warning): each keeps the task from being
    accepted, so ``accepted: false`` always comes with its reason."""
    return [
        _problem(v)
        for v in state.compiler_validations
        if str(getattr(v.status, "value", v.status)).upper()
        in ("ERROR", "FAILED", "WARNING")
    ]


def _problem(validation: Any) -> str:
    """One compiler diagnostic: where, and why (the evidence's reason)."""
    details = validation.details or {}
    where = ".".join(
        str(part)
        for part in (validation.src_package, validation.src_function_name)
        if part
    )
    reasons = [
        " ".join(
            str(part)
            for part in (
                payload.get("decorator"),
                payload.get("param") and f"{payload['param']}:",
                payload.get("reason") or payload.get("issue"),
            )
            if part
        )
        for evidence in details.get("evidence") or []
        for payload in [evidence.get("payload") or {}]
    ]
    why = "; ".join(r for r in reasons if r) or details.get("summary") or ""
    head = f"{validation.check_type}" + (f" on {where}" if where else "")
    return f"{head}: {why or validation.description}"


def _bind(
    task_path: Path, loaded: Any, applied: str, scanned: Any = None
) -> tuple[Any, list[Any], list[str], dict[str, Any]]:
    """The task, its checks, the problems that keep it from running and the
    entities of its reference by canonical id. ``scanned`` (a
    ``runner.source_prep.Scan``) are the reference's entities when the caller
    has read them under the same config (``applied``)."""
    from pythonarchtesting.principles.task import TaskError, bind_task, load_task
    from pythonarchtesting.runner.source_prep import entities_of, prepare_source

    try:
        task = load_task(task_path)
        plain = entities_of(task.reference, loaded, applied, scanned)
        _, checks = bind_task(task, plain)
        compiled = prepare_source(config=loaded, source_path=task_path)
    except TaskError as error:
        return None, [], error.problems, {}
    entities = {e.canonical_id: e for e in plain}
    return task, checks, _problems(compiled), entities


def _not_utf8(task_path: Path, error: UnicodeDecodeError) -> str:
    """Why the task could not be read: the files of ``task_path`` that are
    not UTF-8 (a step read one as UTF-8 although its coding line says
    otherwise). A hidden directory, ``__pycache__`` or a virtual environment
    (``FileConstants.EXCLUDED_DIRS``) is not looked into."""
    import os

    from pythonarchtesting.constants import FileConstants

    found = []
    for root, dirs, names in os.walk(task_path):
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".") and d not in FileConstants.EXCLUDED_DIRS
        ]
        found += [
            Path(root) / name
            for name in names
            if not name.startswith(".") and Path(name).suffix in (".py", ".toml")
        ]
    files = []
    for path in sorted(found):
        if not path.is_file():
            continue
        try:
            path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            files.append(str(path.relative_to(task_path)))
    where = ", ".join(files) or "a file of the task"
    return (
        f"{where} is not UTF-8 ({error.reason} at byte {error.start}): "
        "save the reference as UTF-8"
    )


def _check_cases(
    task: Any,
    checks: list[Any],
    entities: dict[str, Any],
    min_coverage: float,
    policy: Any,
) -> list[dict[str, Any]]:
    judged: dict[str, dict[str, Any]] = {}
    report = []
    for check in checks:
        if check.not_applicable is not None:
            report.append(
                {
                    "role": check.role,
                    "entity": check.entity,
                    "marker": check.marker,
                    "status": "not_applicable",
                    "why": check.not_applicable,
                    "accepted": True,
                }
            )
            continue
        if check.params["cases"] is None:
            continue  # a static check runs no cases (catalog.STATIC_MARKERS)
        if check.entity not in judged:
            judged[check.entity] = judge_cases(
                task.reference,
                entities[check.entity_id],
                check.entity,
                list(check.params["cases"]),
                check.params["init"],
                min_coverage,
                5.0,
                policy,
            )
        found = judged[check.entity]
        report.append(
            {
                "role": check.role,
                "entity": check.entity,
                "marker": check.marker,
                "cases_ran": found["probe_status"] == "completed"
                and all(case["status"] != "error" for case in found["cases"]),
                "coverage": (found["coverage"] or {}).get("ratio"),
                "accepted": found["accepted"],
                "reasons": found["reasons"],
            }
        )
    return report


def _matched(principle: Any, error: Any, results: list[Any]) -> bool:
    """Whether a failed result of the mutant is classified as ``error``."""
    from pythonarchtesting.principles import choose_error, rule_marker

    return any(
        choose_error(principle, str(r.rule_id), fact) is error
        for r in results
        if r.status == "FAILED" and rule_marker(str(r.rule_id)) == error.detected_by
        for fact in (r.details or {}).get("facts") or []
    )


def _run_mutants(
    task: Any,
    loaded: Any,
    mutants: list[Any],
    markers: set[str],
    policy: Any,
    baseline_results: Optional[list[Any]] = None,
    required: Optional[set[str]] = None,
) -> tuple[list[Any], dict[str, list[Any]]]:
    """Results of the unchanged reference and of each mutant, for ``markers``.
    ``baseline_results`` are those of the unchanged reference when the caller
    has run it already (global mode's run of the submission, ``run_and_report``):
    it does not run again for the markers it has results of. A marker of
    ``required`` (default ``markers``: those the task has a check of) with no
    result there runs on the unchanged reference now, since a check with no
    result would count as passed without anything having run."""
    from pythonarchtesting.principles import rule_marker

    given = None
    missing = set(markers)
    if baseline_results is not None:
        given = [r for r in baseline_results if rule_marker(str(r.rule_id)) in markers]
        found = {rule_marker(str(r.rule_id)) for r in given}
        missing = (markers if required is None else required & markers) - found
        if not mutants and not missing:
            return given, {}
    reference = Path(task.reference)
    with tempfile.TemporaryDirectory(prefix="pat-task-") as tmp:
        baseline = Path(tmp) / "reference" / reference.name
        if missing:
            copy_reference(reference, baseline)
        paths = write_mutants(reference, Path(tmp), mutants)
        by_path = _run_copies(
            task, loaded, markers, policy, [baseline] if missing else [], paths
        )
        base = list(given or [])
        if missing:
            base += [
                r
                for r in by_path[baseline.resolve()]
                if rule_marker(str(r.rule_id)) in missing
            ]
        return base, {
            mutant_id: by_path[path.resolve()] for mutant_id, path in paths.items()
        }


def _run_copies(
    task: Any,
    loaded: Any,
    markers: set[str],
    policy: Any,
    baseline: list[Path],
    paths: dict[str, Path],
) -> dict[Path, list[Any]]:
    """The results for ``markers`` of each copy (``baseline``, if any, and the
    mutants' ``paths``) by its resolved path."""
    from pythonarchtesting.principles import rule_marker
    from pythonarchtesting.runner import run_projects

    _, states = run_projects(
        config=loaded,
        source_path=str(task.path),
        targets=[*(str(path) for path in baseline), *(str(p) for p in paths.values())],
        load_config_first=False,
        dynamic=True,
        sandbox=policy,
        rule_filter=lambda rule: rule_marker(str(rule.rule_id)) in markers,
    )
    return {Path(s.target_path).resolve(): list(s.rule_results) for s in states}


def _error_entry(
    principle: Any,
    error: Any,
    chosen: Optional[list[Any]],
    results: dict,
    reference_fails: bool = False,
    dropped: int = 0,
    max_mutants: Optional[int] = None,
) -> dict[str, Any]:
    """The verdict on ``error`` from its ``chosen`` mutants (those
    ``max_mutants`` kept; ``dropped`` is how many of its mutants it left
    out)."""
    entry: dict[str, Any] = {
        "error": error.id,
        "detected_by": error.detected_by,
        "operator": error.operator,
    }
    if reference_fails:
        # The unchanged reference fails the check already (see problems): a
        # mutant it fails proves nothing about the error.
        entry["status"] = "reference_fails"
        entry["mutants"] = len(chosen or [])
        entry["killed"] = 0
        entry["killed_other"] = 0
        entry["signature_matched"] = False
        entry["why"] = (
            f"the unchanged reference fails {error.detected_by} already (see "
            "problems), so no mutant can show that it catches this error"
        )
        return entry
    if not chosen and dropped:
        # Other errors' mutants used up max_mutants: the error has mutants,
        # but none of them ran.
        entry["status"] = "truncated"
        entry["mutants"] = 0
        entry["why"] = (
            f"{error.operator} made {dropped} mutant(s) in the entities "
            f"{error.detected_by} is on, but max_mutants ({max_mutants}) was "
            "used up by the other errors' mutants; raise max_mutants"
        )
        return entry
    if not chosen:
        entry["status"] = "no_mutants"
        entry["why"] = (
            f"{error.operator} found nothing to change in the entities "
            f"{error.detected_by} is on"
        )
        return entry
    outcomes = {
        m.id: mutant_outcome(results[m.id], str(error.detected_by))[0] for m in chosen
    }
    for m in chosen:
        # A kill counts for the error only when a failure is classified as it.
        if outcomes[m.id] == "killed" and not _matched(principle, error, results[m.id]):
            outcomes[m.id] = "killed_other"
    survivors = [m.description for m in chosen if outcomes[m.id] == "survived"]
    not_run = [m.description for m in chosen if outcomes[m.id] == "not_run"]
    killed = sum(1 for outcome in outcomes.values() if outcome == "killed")
    entry["status"] = (
        "survived"
        if survivors
        else "not_run" if not_run else "killed" if killed else "killed_other"
    )
    entry["mutants"] = len(chosen)
    entry["killed"] = killed
    entry["killed_other"] = sum(1 for o in outcomes.values() if o == "killed_other")
    entry["signature_matched"] = killed > 0
    if survivors or not_run:
        entry["survivors"] = (survivors + not_run)[:_SURVIVORS_SHOWN]
    if entry["status"] == "killed_other":
        entry["why"] = (
            f"{error.detected_by} fails on every mutant, but no failure is "
            f"classified as {error.id}: the mutants seed another error"
        )
    return entry


@dataclass(frozen=True)
class _Seeding:
    """The mutants of a task's typical errors: ``seeded``, the errors with an
    operator and a detecting check; ``candidates``, each one's mutants
    anywhere in the reference (``None``: its operator cannot make the call
    its signature names); ``chosen``, those in the entities its check is on;
    ``mutants``, those that run (at most ``max_mutants``, ``truncated`` when
    some were left out); ``skipped``, the files no mutant was made in."""

    seeded: list[Any]
    candidates: dict[str, Optional[list[Any]]]
    chosen: dict[str, list[Any]]
    mutants: list[Any]
    truncated: bool
    skipped: list[tuple[str, str]]

    def ran(self, error: Any) -> list[Any]:
        """The chosen mutants of ``error`` that run."""
        kept = {m.id for m in self.mutants}
        return [m for m in self.chosen.get(error.id, []) if m.id in kept]


def _seed(
    task: Any, checks: list[Any], entities: dict[str, Any], max_mutants: int
) -> _Seeding:
    """Generate the mutants of the task's typical errors and choose those
    that run (``_Seeding``)."""
    from pythonarchtesting.mutation.operators import generate_mutants

    seeded = [e for e in task.principle.errors if e.operator and e.detected_by]
    operators = sorted({str(e.operator) for e in seeded})
    # A collaborator is hardcoded as a class of the modules its check names.
    instantiable = sorted(
        {
            module
            for e in seeded
            if e.operator == "hardcode_collaborator"
            for module in detector_modules(e, checks)
        }
    )
    # A file the operators cannot read (it does not decode or parse) gets no
    # mutant: an error that finds nothing to seed says so (``unread_files_note``).
    skipped: list[tuple[str, str]] = []
    every = (
        generate_mutants(
            Path(task.reference),
            operators,
            parameter_classes=parameter_classes(checks, entities),
            instantiable=instantiable,
            spied=spied(checks, entities),
            skipped=skipped,
        )
        if operators
        else []
    )
    candidates = {
        e.id: seed_candidates(e, every, named_callees(e, checks)) for e in seeded
    }
    chosen = {
        e.id: mutants_for(
            e,
            found,
            aimed_entities(e, checks, entities),
            detector_modules(e, checks),
        )
        for e in seeded
        if (found := candidates[e.id])
    }
    unique = {m.id for found in chosen.values() for m in found}
    # In turn from each error, so that max_mutants leaves none without a
    # mutant while there are no more errors than mutants.
    mutants = in_turn(
        [sorted(found, key=lambda m: m.id) for found in chosen.values()],
        max_mutants,
    )
    return _Seeding(
        seeded, candidates, chosen, mutants, len(unique) > max_mutants, skipped
    )


def _error_report(
    principle: Any,
    error: Any,
    checks: list[Any],
    seeding: _Seeding,
    failing: set[str],
    results: dict[str, list[Any]],
    max_mutants: int,
) -> dict[str, Any]:
    """The verdict on one typical error of the principle (module docstring)."""
    untargeted = untargeted_reason(error, checks) if error.detected_by else None
    if error.gap is not None:
        return {"error": error.id, "status": "gap", "gap": error.gap}
    if untargeted is not None:
        return {
            "error": error.id,
            "detected_by": error.detected_by,
            "operator": error.operator,
            "status": "not_applicable",
            "why": f"{untargeted}; the error was not verified by a mutant",
        }
    if error.operator is None:
        return {
            "error": error.id,
            "detected_by": error.detected_by,
            "status": "not_verifiable_by_mutation",
        }
    candidates = seeding.candidates[error.id]
    if candidates is None:
        return {
            "error": error.id,
            "detected_by": error.detected_by,
            "operator": error.operator,
            "status": "not_verifiable_by_mutation",
            "why": unseedable_reason(error, checks),
        }
    if str(error.detected_by) in failing:
        return _error_entry(
            principle, error, seeding.ran(error), results, reference_fails=True
        )
    if not candidates:
        return {
            "error": error.id,
            "detected_by": error.detected_by,
            "operator": error.operator,
            "status": "not_applicable",
            "why": (
                f"the reference contains no {missing_site(error)}; the error was "
                "not verified by a mutant" + unread_files_note(seeding.skipped)
            ),
        }
    mine = seeding.chosen.get(error.id, [])
    ran = seeding.ran(error)
    entry = _error_entry(
        principle,
        error,
        ran,
        results,
        dropped=len(mine) - len(ran),
        max_mutants=max_mutants,
    )
    if entry["status"] == "no_mutants":
        entry["why"] += unread_files_note(seeding.skipped)
    return entry


def _verify_errors(
    task: Any,
    loaded: Any,
    checks: list[Any],
    entities: dict[str, Any],
    max_mutants: int,
    policy: Any,
    baseline: Optional[list[Any]] = None,
) -> dict[str, Any]:
    """Run the mutants of the task's typical errors and the unchanged
    reference by the task's checks, and judge each error."""
    principle = task.principle
    seeding = _seed(task, checks, entities, max_mutants)
    # The unchanged reference runs every check, also with no mutant at all
    # and for a marker no error seeds: a check it fails rejects the task.
    markers = {str(e.detected_by) for e in seeding.seeded} | {
        str(c.marker) for c in checks
    }
    base, results = (
        _run_mutants(
            task,
            loaded,
            seeding.mutants,
            markers,
            policy,
            baseline,
            required={str(c.marker) for c in checks},
        )
        if markers
        else ([], {})
    )
    reference_passes = all(
        mutant_outcome(base, marker)[0] == "survived" for marker in markers
    )
    failing = {
        marker for marker in markers if mutant_outcome(base, marker)[0] != "survived"
    }
    return {
        "reference_passes": reference_passes,
        "truncated": seeding.truncated,
        "errors": [
            _error_report(
                principle, error, checks, seeding, failing, results, max_mutants
            )
            for error in principle.errors
        ],
        "reference_problems": _reference_problems(base, markers),
    }


def _warnings(task: Any, checks: list[Any], entities: dict[str, Any]) -> list[str]:
    """``WARNING:`` lines that keep no task from being accepted: an
    instantiation check that is not applicable because its ``target_role``
    binds only functions, while their modules define classes the teacher may
    have meant (a strategy role that binds functions beside a ``Strategy``
    class)."""
    from pythonarchtesting.principles.catalog import INSTANCE_TARGET_MARKERS

    found: list[str] = []
    for template in task.principle.checks:
        role = template.target_role
        if template.marker not in INSTANCE_TARGET_MARKERS or role is None:
            continue
        if not any(
            c.marker == template.marker and c.not_applicable is not None for c in checks
        ):
            continue
        names = set(task.roles.get(role, ()))
        modules = {
            str(e.module_path)
            for e in entities.values()
            if (e.kind == "function" and f"{e.module_path}.{e.qualname}" in names)
            or (e.kind == "module" and str(e.module_path) in names)
        }
        classes = sorted(
            f"{e.module_path}.{e.qualname}"
            for e in entities.values()
            if e.kind == "class" and str(e.module_path) in modules
        )
        if classes:
            found.append(
                f"WARNING: role {role!r} binds only functions, but their "
                f"module also defines classes ({', '.join(classes)}): "
                f"{template.marker} (role {template.role!r}) is not_applicable, "
                "so code that builds such an object itself is not caught; "
                "bind the classes (module.Class) if they are the "
                f"{role} (the task is not rejected for this)"
            )
    return found


def _reference_problems(base: list[Any], markers: set[str]) -> list[str]:
    """Why the unchanged reference fails a check, or why a check did not run
    on it: one line per such rule (a static check runs no cases, so nothing
    else says it)."""
    from pythonarchtesting.principles import rule_marker

    problems: list[str] = []
    for r in base:
        marker = rule_marker(str(r.rule_id))
        if marker not in markers:
            continue
        why = str((r.details or {}).get("summary") or r.message)
        if did_not_run(r):
            reason = (r.details or {}).get("reason")
            problems.append(
                f"{marker} did not run on the reference"
                + (f" ({reason})" if reason else "")
                + f": {why}"
            )
        elif r.status == "FAILED":
            problems.append(f"{marker} fails on the reference: {why}")
    return problems


def verify_task(
    task_path: Path,
    config: Optional[str],
    policy: Any,
    min_coverage: float,
    max_mutants: int,
    *,
    scanned: Any = None,
    baseline: Optional[list[Any]] = None,
) -> dict[str, Any]:
    """Validate the task at ``task_path``, run its cases and verify by mutation
    that its checks catch the principle's typical errors (module docstring),
    under the config ``resolve_config`` finds (or ``config``); ``policy`` is
    the sandbox of the runs (``runner.settings.sandbox_policy``).

    ``scanned`` are the reference's entities when the caller has read them
    (``runner.source_prep.Scan``; read again under another config), and
    ``baseline`` the results of the unchanged reference run by the task's
    checks (the target states' ``rule_results`` of a run over an unchanged
    copy), which the mutation check then does not run again."""
    try:
        loaded, applied = resolve_config(task_path, config)
        task, checks, problems, entities = _bind(task_path, loaded, applied, scanned)
        result: dict[str, Any] = {
            "task_dir": str(task_path),
            "principle": task.principle.id if task is not None else None,
            "config": applied,
            "accepted": False,
            "problems": problems,
            "checks": [],
            "errors": [],
        }
        if task is None or problems:
            return result
        result["checks"] = _check_cases(task, checks, entities, min_coverage, policy)
        verified = _verify_errors(
            task, loaded, checks, entities, int(max_mutants), policy, baseline
        )
        result["problems"] = verified.pop("reference_problems") + _warnings(
            task, checks, entities
        )
        result.update(verified)
    except UnicodeDecodeError as exc:
        raise InvalidInputError(_not_utf8(task_path, exc)) from exc
    result["accepted"] = (
        all(check["accepted"] for check in result["checks"])
        and result["reference_passes"]
        and not result["truncated"]
        and all(
            e["status"]
            in ("killed", "not_verifiable_by_mutation", "not_applicable", "gap")
            for e in result["errors"]
        )
    )
    return result


__all__ = ["verify_task"]
