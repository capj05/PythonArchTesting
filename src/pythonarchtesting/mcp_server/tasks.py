"""MCP tool ``prepare_task``: check a task an AI client wrote for a principle.

A task (``principles.task``) is ``task.toml`` next to an unannotated
reference: the principle, its roles bound to entities, and the cases of each
entity. ``prepare_task`` answers, deterministically, whether the task is ready
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
   A mutant never counts as killed by a check the unchanged reference
   already fails: the error is ``reference_fails``.
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
   binds the role to other code than the one the error lives in.

Nothing is written into the task: the mutants live in a temporary directory.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.exceptions import ConfigurationError
from pythonarchtesting.mcp_server.authoring import (
    DEFAULT_MAX_MUTANTS,
    DEFAULT_MIN_COVERAGE,
    _in_range,
    _judge,
    judge_cases,
)
from pythonarchtesting.mcp_server.errors import ToolInputError, require_absolute
from pythonarchtesting.mcp_server.evaluation import (
    DEFAULT_SANDBOX_MEMORY_MB,
    _sandbox_policy,
    resolve_config,
)

# The call each call-seeding operator inserts, for the callee an error's
# signature names: ``add_io_call`` any of the three I/O calls,
# ``add_io_via_helper`` only print, ``add_builtin_call`` also a type test.
_IO_MEMBERS = {
    "add_io_call": {
        "builtins:print": "print",
        "builtins:input": "input",
        "io:open": "open",
    },
    "add_io_via_helper": {"builtins:print": "print"},
    "add_builtin_call": {
        "builtins:print": "print",
        "builtins:input": "input",
        "io:open": "open",
        "builtins:isinstance": "isinstance",
        "builtins:type": "type",
    },
}
# What in the reference each operator needs, for a ``not_applicable`` error.
_SITES = {
    "foreign_write": "data attribute of an object a function gets from outside",
    "mutate_private_container": (
        "private container (a dict, list or set an owner's constructor creates) "
        "of an object a function gets as a parameter"
    ),
    "mutate_public_container": (
        "public container (a dict, list or set an owner's constructor creates) "
        "of an object a function gets as a parameter"
    ),
    "read_private_attribute": (
        "private data attribute of an object of a project class a function "
        "gets as a parameter"
    ),
    "stub_role_call": "call of a function of another project module",
    "add_io_call": "function whose body starts on a line of its own",
    "add_io_via_helper": "function whose body starts on a line of its own",
    "add_builtin_call": "function whose body starts on a line of its own",
    "drop_base": "class that names a base other than object",
    "hardcode_collaborator": (
        "constructor that keeps a collaborator it is given (self.x = x) together "
        "with a class of the check's modules that can be built without arguments"
    ),
    "concretize_base": (
        "abstract class (ABC, Protocol or ABCMeta among its bases, or an "
        "@abstractmethod method)"
    ),
}
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


def _bind(task_path: Path, loaded: Any) -> tuple[Any, list[Any], list[str]]:
    """The task, its checks and the problems that keep it from running."""
    from pythonarchtesting.principles.task import TaskError, bind_task, load_task
    from pythonarchtesting.runner.source_prep import prepare_source

    try:
        task = load_task(task_path)
        plain = prepare_source(config=loaded, source_path=task.reference)
        _, checks = bind_task(task, plain.source_entities)
        compiled = prepare_source(config=loaded, source_path=task_path)
    except TaskError as error:
        return None, [], error.problems
    return task, checks, _problems(compiled)


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


def _aimed(error: Any, checks: list[Any], entities: dict[str, Any]) -> set[Any]:
    """``(file, qualname)`` of the entities the check detecting ``error`` is on."""
    return {
        (str(entities[c.entity_id].filepath_rel), str(entities[c.entity_id].qualname))
        for c in checks
        if c.marker == error.detected_by and c.not_applicable is None
    }


def _targets(error: Any, checks: list[Any]) -> set[str]:
    """The modules the check detecting ``error`` names (with ``target_role``,
    those of the entities bound to that role, or their classes)."""
    return {
        str(module)
        for c in checks
        if c.marker == error.detected_by
        for module in c.params["modules"]
    }


def _not_applicable(error: Any, checks: list[Any]) -> Optional[str]:
    """Why the check detecting ``error`` has nothing to check in the task,
    when it has not on any entity (``TaskCheck.not_applicable``)."""
    mine = [c for c in checks if c.marker == error.detected_by]
    if mine and all(c.not_applicable is not None for c in mine):
        return str(mine[0].not_applicable)
    return None


def spied(
    checks: list[Any], entities: dict[str, Any]
) -> dict[tuple[str, str], set[str]]:
    """The constructor parameters the task gives a spy: ``(file, class) ->
    parameter names`` for each ``{"$spy": ...}`` in the ``init`` of a
    method's checks, positional (after ``self``) or by keyword."""
    import ast

    found: dict[tuple[str, str], set[str]] = {}
    for check in checks:
        entity = entities.get(check.entity_id)
        init = check.params.get("init")
        if entity is None or entity.kind != "method" or not isinstance(init, dict):
            continue
        owner = str(entity.qualname).rpartition(".")[0]
        file = str(entity.filepath_rel)
        names: list[str] = []
        for other in entities.values():
            node = other.extras.get("ast_node")
            if (
                str(other.filepath_rel) == file
                and str(other.qualname) == f"{owner}.__init__"
                and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ):
                names = [a.arg for a in node.args.posonlyargs + node.args.args][1:]
                names += [a.arg for a in node.args.kwonlyargs]
        given = list(zip(names, init.get("args") or []))
        given += list((init.get("kwargs") or {}).items())
        params = found.setdefault((file, owner), set())
        params.update(
            name for name, value in given if isinstance(value, dict) and "$spy" in value
        )
    return found


def _callees(error: Any, checks: list[Any]) -> list[str]:
    """The callees (``builtins:isinstance``) the check detecting ``error``
    names (``builtins.isinstance``)."""
    found: list[str] = []
    for module in sorted(_targets(error, checks)):
        head, _, last = module.rpartition(".")
        if head and f"{head}:{last}" not in found:
            found.append(f"{head}:{last}")
    return found


def _candidates(
    error: Any, mutants: list[Any], callees: Optional[list[str]] = None
) -> Optional[list[Any]]:
    """The mutants of ``error``'s operator anywhere in the reference (of a
    call-seeding operator, those making the call its signature names, or
    without one, a call of the ``callees`` its check names); ``None`` when
    the operator cannot make that call."""
    members: Optional[set[str]] = None
    callee = error.signature.callee if error.signature else None
    if error.operator in _IO_MEMBERS:
        wanted = [callee] if callee is not None else list(callees or [])
        if wanted:
            members = {
                _IO_MEMBERS[error.operator][c]
                for c in wanted
                if c in _IO_MEMBERS[error.operator]
            }
            if not members:
                return None
    return [
        m
        for m in mutants
        if m.operator == error.operator and (members is None or m.member in members)
    ]


# Operators that change a constructor: a check on a method sees the change,
# because the method's cases build its object first. ``rebuild_injected``
# also changes a constructor, but no catalogue error seeds with it, and its
# mutants name no ``function`` to aim by.
_CONSTRUCTOR_OPERATORS = frozenset({"hardcode_collaborator"})


def _in_aimed(mutant: Any, aimed: set[Any]) -> bool:
    if (mutant.file, mutant.function) in aimed:
        return True
    if mutant.operator not in _CONSTRUCTOR_OPERATORS:
        return False
    owner, _, method = str(mutant.function).rpartition(".")
    return method == "__init__" and any(
        file == mutant.file and str(qualname).startswith(f"{owner}.")
        for file, qualname in aimed
    )


def _mutants_for(
    error: Any, candidates: list[Any], aimed: set[Any], targets: set[str]
) -> list[Any]:
    """The ``candidates`` that seed ``error`` where its check looks. A mutant
    of ``stub_role_call`` stops the calls into a module the check names; one
    of a constructor operator changes the constructor of a method's class."""
    members = targets if error.operator == "stub_role_call" else None
    return [
        m
        for m in candidates
        if _in_aimed(m, aimed) and (members is None or m.member in members)
    ]


def parameter_classes(
    checks: list[Any], entities: dict[str, Any]
) -> dict[tuple[str, str], dict[str, str]]:
    """What the cases of the task's checks build for each function's
    parameters: ``(file, qualname) -> {parameter: class name}`` for every
    argument that is a project object (``{"$new": "inventory.Inventory"}``),
    positional (after ``self`` for a method) or by keyword."""
    import ast

    found: dict[tuple[str, str], dict[str, str]] = {}
    for check in checks:
        entity = entities.get(check.entity_id)
        if entity is None or check.params["cases"] is None:
            continue
        node = entity.extras.get("ast_node")
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = [a.arg for a in node.args.posonlyargs + node.args.args]
        if entity.kind == "method":
            names = names[1:]
        classes = found.setdefault((str(entity.filepath_rel), str(entity.qualname)), {})
        for case in check.params["cases"]:
            if not isinstance(case, dict):
                continue
            given = list(zip(names, case.get("args") or []))
            given += list((case.get("kwargs") or {}).items())
            for name, value in given:
                if isinstance(value, dict) and isinstance(value.get("$new"), str):
                    classes.setdefault(name, value["$new"].rpartition(".")[2])
    return found


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
    task: Any, loaded: Any, mutants: list[Any], markers: set[str], policy: Any
) -> tuple[list[Any], dict[str, list[Any]]]:
    """Results of the unchanged reference and of each mutant, for ``markers``."""
    from pythonarchtesting.principles import rule_marker
    from pythonarchtesting.runner import run_projects

    reference = Path(task.reference)
    ignore = shutil.ignore_patterns("__pycache__", ".*")
    with tempfile.TemporaryDirectory(prefix="pat-task-") as tmp:
        baseline = Path(tmp) / "reference" / reference.name
        shutil.copytree(reference, baseline, ignore=ignore)
        paths: dict[str, Path] = {}
        for mutant in mutants:
            copy = Path(tmp) / mutant.id / reference.name
            shutil.copytree(reference, copy, ignore=ignore)
            (copy / mutant.file).write_text(mutant.source, encoding="utf-8")
            for other, text in mutant.also:
                (copy / other).write_text(text, encoding="utf-8")
            paths[mutant.id] = copy
        _, states = run_projects(
            config=loaded,
            source_path=str(task.path),
            targets=[str(baseline), *(str(path) for path in paths.values())],
            load_config_first=False,
            dynamic=True,
            sandbox=policy,
            rule_filter=lambda rule: rule_marker(str(rule.rule_id)) in markers,
        )
        by_path = {Path(s.target_path).resolve(): list(s.rule_results) for s in states}
        return by_path[baseline.resolve()], {
            mutant_id: by_path[path.resolve()] for mutant_id, path in paths.items()
        }


def _error_entry(
    principle: Any,
    error: Any,
    chosen: Optional[list[Any]],
    results: dict,
    reference_fails: bool = False,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "error": error.id,
        "detected_by": error.detected_by,
        "operator": error.operator,
    }
    if not chosen:
        entry["status"] = "no_mutants"
        entry["why"] = (
            f"{error.operator} found nothing to change in the entities "
            f"{error.detected_by} is on"
        )
        return entry
    if reference_fails:
        # The unchanged reference fails the check already (see problems): a
        # mutant it fails proves nothing about the error.
        entry["status"] = "reference_fails"
        entry["mutants"] = len(chosen)
        entry["killed"] = 0
        entry["killed_other"] = 0
        entry["signature_matched"] = False
        entry["why"] = (
            f"the unchanged reference fails {error.detected_by} already (see "
            "problems), so no mutant can show that it catches this error"
        )
        return entry
    outcomes = {m.id: _judge(results[m.id], str(error.detected_by))[0] for m in chosen}
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


def _verify_errors(
    task: Any,
    loaded: Any,
    checks: list[Any],
    entities: dict[str, Any],
    max_mutants: int,
    policy: Any,
) -> dict[str, Any]:
    from pythonarchtesting.mutation.operators import generate_mutants

    principle = task.principle
    seeded = [e for e in principle.errors if e.operator and e.detected_by]
    operators = sorted({str(e.operator) for e in seeded})
    # A collaborator is hardcoded as a class of the modules its check names.
    instantiable = sorted(
        {
            module
            for e in seeded
            if e.operator == "hardcode_collaborator"
            for module in _targets(e, checks)
        }
    )
    every = (
        generate_mutants(
            Path(task.reference),
            operators,
            parameter_classes=parameter_classes(checks, entities),
            instantiable=instantiable,
            spied=spied(checks, entities),
        )
        if operators
        else []
    )
    candidates = {e.id: _candidates(e, every, _callees(e, checks)) for e in seeded}
    chosen = {
        e.id: _mutants_for(e, found, _aimed(e, checks, entities), _targets(e, checks))
        for e in seeded
        if (found := candidates[e.id])
    }
    unique = {m.id: m for found in chosen.values() for m in found}
    truncated = len(unique) > max_mutants
    mutants = sorted(unique.values(), key=lambda m: m.id)[:max_mutants]
    kept = {m.id for m in mutants}
    markers = {str(e.detected_by) for e in seeded}
    base, results = (
        _run_mutants(task, loaded, mutants, markers, policy) if mutants else ([], {})
    )
    reference_passes = all(_judge(base, marker)[0] == "survived" for marker in markers)
    failing = {marker for marker in markers if _judge(base, marker)[0] != "survived"}
    report = []
    for error in principle.errors:
        untargeted = _not_applicable(error, checks) if error.detected_by else None
        if error.gap is not None:
            report.append({"error": error.id, "status": "gap", "gap": error.gap})
        elif untargeted is not None:
            report.append(
                {
                    "error": error.id,
                    "detected_by": error.detected_by,
                    "operator": error.operator,
                    "status": "not_applicable",
                    "why": f"{untargeted}; the error was not verified by a mutant",
                }
            )
        elif error.operator is None:
            report.append(
                {
                    "error": error.id,
                    "detected_by": error.detected_by,
                    "status": "not_verifiable_by_mutation",
                }
            )
        elif candidates[error.id] is None:
            report.append(
                {
                    "error": error.id,
                    "detected_by": error.detected_by,
                    "operator": error.operator,
                    "status": "not_verifiable_by_mutation",
                    "why": (
                        f"{error.operator} cannot seed a call of "
                        f"{error.signature.callee}"
                    ),
                }
            )
        elif not candidates[error.id]:
            site = _SITES.get(str(error.operator), "place to seed the error")
            report.append(
                {
                    "error": error.id,
                    "detected_by": error.detected_by,
                    "operator": error.operator,
                    "status": "not_applicable",
                    "why": (
                        f"the reference contains no {site}; the error was not "
                        "verified by a mutant"
                    ),
                }
            )
        else:
            report.append(
                _error_entry(
                    principle,
                    error,
                    [m for m in chosen[error.id] if m.id in kept],
                    results,
                    reference_fails=str(error.detected_by) in failing,
                )
            )
    return {
        "reference_passes": reference_passes,
        "truncated": truncated,
        "errors": report,
        "reference_problems": _reference_problems(base, markers),
    }


def _reference_problems(base: list[Any], markers: set[str]) -> list[str]:
    """Why the unchanged reference fails a check: one line per failed rule
    (a static check runs no cases, so nothing else says it)."""
    from pythonarchtesting.principles import rule_marker

    return [
        f"{rule_marker(str(r.rule_id))} fails on the reference: "
        + str((r.details or {}).get("summary") or r.message)
        for r in base
        if r.status == "FAILED" and rule_marker(str(r.rule_id)) in markers
    ]


def prepare_task(
    task_dir: str,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
    max_mutants: int = DEFAULT_MAX_MUTANTS,
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
) -> dict[str, Any]:
    """Validate the task at ``task_dir``, run its cases and verify by mutation
    that its checks catch the principle's typical errors (module docstring)."""
    from pythonarchtesting.principles.task import is_task
    from pythonarchtesting.runner.source_prep import prepare_source

    task_path = require_absolute(task_dir, "task_dir")
    if not is_task(task_path):
        raise ToolInputError(f"no task.toml in {task_dir}")
    if not _in_range(min_coverage, 0.0, 1.0):
        raise ToolInputError("min_coverage must be a number in [0, 1]")
    if not _in_range(max_mutants, 1, 200) or int(max_mutants) != max_mutants:
        raise ToolInputError("max_mutants must be a whole number in [1, 200]")
    policy = _sandbox_policy(True, sandbox, sandbox_memory_mb)
    try:
        loaded, applied = resolve_config(task_path, config)
        task, checks, problems = _bind(task_path, loaded)
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
        entities = {
            e.canonical_id: e
            for e in prepare_source(
                config=loaded, source_path=task.reference
            ).source_entities
        }
        result["checks"] = _check_cases(task, checks, entities, min_coverage, policy)
        verified = _verify_errors(
            task, loaded, checks, entities, int(max_mutants), policy
        )
        result["problems"] = verified.pop("reference_problems")
        result.update(verified)
    except (ConfigurationError, OSError) as exc:
        raise ToolInputError(str(exc)) from exc
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


__all__ = ["prepare_task"]
