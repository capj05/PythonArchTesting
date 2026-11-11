"""MCP tools that check what an LLM client proposes for a reference (F4).

The server never calls an LLM. A client proposes something (the cases that
drive a runtime check, a marker); these tools run it on the reference and say
deterministically whether it holds, so the client can iterate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.exceptions import ConfigurationError
from pythonarchtesting.mcp_server.errors import ToolInputError, require_absolute
from pythonarchtesting.mcp_server.evaluation import (
    DEFAULT_SANDBOX_MEMORY_MB,
    _sandbox_policy,
    resolve_config,
)

DEFAULT_MIN_COVERAGE = 0.8


def _in_range(value: Any, low: float, high: float) -> bool:
    """Whether ``value`` is a real number (not a bool) within ``[low, high]``."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and low <= value <= high
    )


def _reference_entities(source_path: Path, config: Optional[str]) -> list[Any]:
    from pythonarchtesting.runner.source_prep import prepare_source

    try:
        loaded, _ = resolve_config(source_path, config)
        state = prepare_source(config=loaded, source_path=source_path)
    except (ConfigurationError, OSError) as exc:
        raise ToolInputError(str(exc)) from exc
    return list(state.source_by_id.values())


def check_cases(
    source: str,
    entry: str,
    cases: list[dict[str, Any]],
    init: Optional[dict[str, Any]] = None,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
    timeout_s: float = 5.0,
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
) -> dict[str, Any]:
    """Run proposed ``cases`` of ``entry`` on the reference and judge them.

    The cases are accepted when every case could be set up and run (an
    exception the reference raises on purpose is fine and reported) and the
    lines of ``entry`` that the cases ran are at least ``min_coverage`` of
    all its lines. The calls between modules they drove are returned too:
    that is what a runtime check built on these cases will see.
    """
    from pythonarchtesting.rules.compilation.decorators.module_structure import (
        entry_problem,
    )

    source_path = require_absolute(source, "source")
    _not_a_task(source_path, "check_cases")
    if not _in_range(min_coverage, 0.0, 1.0):
        raise ToolInputError("min_coverage must be a number in [0, 1]")
    params = {"entry": entry, "cases": cases, "init": init, "timeout_s": timeout_s}
    problem, entity = entry_problem(
        params, _reference_entities(source_path, config), "check_cases"
    )
    if problem is None and entity is None:
        problem = ("entry", "give the reference function as 'module.function'")
    if problem is not None:
        raise ToolInputError(f"{problem[0]}: {problem[1]}")
    assert entity is not None  # nosec B101 - narrowed by the checks above
    policy = _sandbox_policy(True, sandbox, sandbox_memory_mb)
    return judge_cases(
        source_path, entity, entry, cases, init, min_coverage, timeout_s, policy
    )


def _not_a_task(source_path: Path, tool: str) -> None:
    from pythonarchtesting.principles.task import is_task

    if is_task(source_path):
        raise ToolInputError(
            f"source is a task directory (task.toml): give {tool} the reference "
            "directory itself, or check the whole task with prepare_task"
        )


def judge_cases(
    source_path: Path,
    entity: Any,
    entry: str,
    cases: list[dict[str, Any]],
    init: Optional[dict[str, Any]],
    min_coverage: float,
    timeout_s: float,
    policy: Any,
) -> dict[str, Any]:
    """Run ``cases`` of the reference ``entity`` (named ``entry``) and judge
    them as ``check_cases`` does."""
    from pythonarchtesting.dynamic.runner import run_cases
    from pythonarchtesting.execution.evaluators.runtime_structure import (
        _coverage,
        _edges,
    )

    outcome = run_cases(
        target_root=source_path,
        module_path=entity.module_path,
        qualname=entity.qualname,
        kind=entity.kind,
        cases=cases,
        init=init,
        timeout_s=float(timeout_s),
        sandbox=policy,
        observe={"calls": "edges"},
    )
    reasons: list[str] = []
    if outcome.status != "completed":
        reasons.append(f"the reference did not run: {outcome.status}: {outcome.error}")
    reported = [
        {
            "index": case.get("index"),
            "status": case.get("status"),
            "failures": list(case.get("failures") or []),
            **({"raised": case["raised"]} if case.get("raised") else {}),
        }
        for case in outcome.cases
    ]
    for case in reported:
        if case["status"] == "error":
            reasons.append(f"case {case['index']} could not run: {case['failures']}")
    coverage = _coverage(list(outcome.cases))
    if coverage is not None:
        total = coverage["lines_total"]
        coverage["ratio"] = round(coverage["lines_run"] / total, 3) if total else 1.0
        if coverage["ratio"] < float(min_coverage):
            reasons.append(
                f"coverage {coverage['ratio']:.0%} of {entry} is below "
                f"{float(min_coverage):.0%}; add cases for lines "
                f"{coverage['unexercised_lines']}"
            )
    edges = sorted({f"{a} -> {b}" for case in outcome.cases for a, b in _edges(case)})
    result: dict[str, Any] = {
        "accepted": not reasons,
        "reasons": reasons,
        "entry": entry,
        "probe_status": outcome.status,
        "cases": reported,
        "coverage": coverage,
        "edges": edges,
    }
    if outcome.stderr and reasons:
        result["stderr_tail"] = outcome.stderr
    return result


def describe_architecture(
    source: str,
    mode: str = "static",
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
) -> dict[str, Any]:
    """The reference's architecture model (F4.1); see ``architecture.model``."""
    from pythonarchtesting.architecture.model import MODES, describe
    from pythonarchtesting.runner.source_prep import prepare_source

    # Resolved as the evaluation resolves it: the package name is its last part.
    source_path = require_absolute(source, "source").resolve()
    if mode not in MODES:
        raise ToolInputError(f"mode must be one of {', '.join(MODES)}: {mode}")
    policy = _sandbox_policy(mode == "full", sandbox, sandbox_memory_mb)
    try:
        loaded, _ = resolve_config(source_path, config)
        state = prepare_source(config=loaded, source_path=source_path)
    except (ConfigurationError, OSError) as exc:
        raise ToolInputError(str(exc)) from exc
    return describe(state, mode=mode, source_root=source_path, sandbox=policy)


DEFAULT_MAX_MUTANTS = 100
# A rule that ended for one of these reasons observed nothing: not a kill.
_NOT_RUN = ("case_setup_failed", "reference_failed", "target_kind_mismatch")


def _rule_matches(rule_id: str, rule: str) -> bool:
    parts = rule_id.split("/")
    return rule_id.startswith(rule) or (len(parts) > 1 and parts[1] == rule)


def _did_not_run(result: Any) -> bool:
    reason = str((result.details or {}).get("reason") or "")
    return result.status == "ERROR" or (
        result.status == "FAILED"
        and (reason.startswith("probe_") or reason in _NOT_RUN)
    )


def _judge(results: list[Any], rule: str) -> tuple[str, list[str], list[str]]:
    """``killed``/``survived``/``not_run`` for one target, failing ids, summaries."""
    matching = [r for r in results if _rule_matches(str(r.rule_id), rule)]
    # A part that was SKIPPED by design (runtime without dynamic) says
    # nothing; it matters only when no part of the rule ran at all.
    ours = [r for r in matching if r.status != "SKIPPED"] or matching
    failed = [r for r in ours if r.status == "FAILED" and not _did_not_run(r)]
    if failed:
        return (
            "killed",
            sorted({str(r.rule_id) for r in failed}),
            [str((r.details or {}).get("summary") or "") for r in failed][:3],
        )
    broken = [r for r in ours if _did_not_run(r) or r.status == "SKIPPED"]
    if broken:
        return (
            "not_run",
            sorted({str(r.rule_id) for r in broken}),
            [str((r.details or {}).get("summary") or "") for r in broken][:3],
        )
    return "survived", [], []


def _sample(mutants: list[Any], limit: int) -> list[Any]:
    """Up to ``limit`` mutants, taken in turn from each operator."""
    by_operator: dict[str, list[Any]] = {}
    for mutant in mutants:
        by_operator.setdefault(mutant.operator, []).append(mutant)
    return _in_turn(list(by_operator.values()), limit)


def _in_turn(groups: list[list[Any]], limit: int) -> list[Any]:
    """Up to ``limit`` mutants, taken in turn from each of ``groups``; a
    mutant in several groups (the same ``id``) is taken once, and the group
    whose turn it is takes its next one instead."""
    queues = [list(group) for group in groups]
    chosen: list[Any] = []
    taken: set[str] = set()
    while len(chosen) < limit and any(queues):
        for queue in queues:
            while queue and queue[0].id in taken:
                queue.pop(0)
            if queue and len(chosen) < limit:
                mutant = queue.pop(0)
                taken.add(mutant.id)
                chosen.append(mutant)
    return chosen


# The operators that seed a violation each marker can see; a marker missing
# here has none, so its operators must be given.
_OPERATORS_BY_MARKER: dict[str, tuple[str, ...]] = {
    "forbid_imports": ("add_import", "lazy_import", "add_library", "dynamic_import"),
    "enforce_layers": ("add_import", "lazy_import"),
    "forbid_cycles": ("add_import", "lazy_import"),
    "architecture_entry": (
        "add_import",
        "lazy_import",
        "add_library",
        "dynamic_import",
        "rebuild_injected",
        "drop_call",
    ),
    "forbid_runtime_instantiation": ("rebuild_injected",),
    # A delegation marker injects a spy, which cannot be rebuilt from its
    # class: only its calls are cut out.
    "require_runtime_delegation": ("drop_call",),
    "require_runtime_calls": ("drop_call",),
    "forbid_runtime_imports": ("add_library", "dynamic_import"),
    "module_interface": ("use_private_name",),
    "forbid_foreign_writes": ("foreign_write",),
    "forbid_private_access": ("read_private_attribute",),
    "implements_protocol": ("break_port",),
    "implements_runtime_protocol": ("break_port",),
    "enforce_reference_calls": ("drop_call", "rebuild_injected"),
    "subclass_of": ("drop_base",),
    "is_abstract_class": ("concretize_base",),
}
_DETAILS = ("problems", "all")
_RUNTIME_ONLY = "<runtime only>"


def _spied_parameter(source_path: Path, entity: Any, params: dict[str, Any]) -> str:
    """The constructor parameter of ``entity``'s class that receives the
    delegation marker's spy, or the spy's name when it cannot be told."""
    import ast

    spy = str(params.get("spy") or "")
    init = params.get("init") or {}
    owner = str(entity.qualname).split(".")[0]
    try:
        tree = ast.parse(
            (source_path / str(entity.filepath_rel)).read_text(encoding="utf-8")
        )
    except (OSError, SyntaxError, ValueError):
        return spy
    for key, value in (init.get("kwargs") or {}).items():
        if value == {"$spy": spy}:
            return str(key)
    position = next(
        (i for i, value in enumerate(init.get("args") or []) if value == {"$spy": spy}),
        None,
    )
    if position is None:
        return spy
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == owner:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    names = [a.arg for a in item.args.posonlyargs + item.args.args][1:]
                    if position < len(names):
                        return names[position]
    return spy


def _delegations(
    source_path: Path, state: Any, matching: list[Any]
) -> set[tuple[str, str, str]]:
    """``(class, constructor parameter, member)`` each delegation marker among
    ``matching`` requires a call to (member ``""``: any)."""
    found: set[tuple[str, str, str]] = set()
    for r in matching:
        if str(r.rule_id).split("/")[1] != "require_runtime_delegation":
            continue
        entity = state.source_by_id.get(r.selector.source_entity_id)
        if entity is None or entity.kind != "method":
            continue
        found.add(
            (
                str(entity.qualname).split(".")[0],
                _spied_parameter(source_path, entity, dict(r.params)),
                str(r.params.get("member") or ""),
            )
        )
    return found


def _scope(
    source_path: Path, rule: str, config: Optional[str]
) -> tuple[
    set[str], Optional[set[str]], dict[str, list[str]], set[tuple[str, str, str]]
]:
    """The markers ``rule`` names in the reference, the files they are about,
    and the modules and libraries they forbid, per file (empty when ``rule``
    names other markers too).

    ``None`` for files: a marker on the root package states something of the
    whole project, so every file is fair game. The forbidden names are those
    of ``forbid_imports`` / ``forbid_runtime_imports``: the libraries among
    them are what ``add_library`` imports, and an import mutant of a name no
    marker of its file forbids is no violation of these markers.
    """
    from pythonarchtesting.runner.source_prep import prepare_source

    try:
        loaded, _ = resolve_config(source_path, config)
        state = prepare_source(config=loaded, source_path=source_path)
    except (ConfigurationError, OSError) as exc:
        raise ToolInputError(str(exc)) from exc
    matching = [
        r
        for r in state.rules
        if _rule_matches(str(r.rule_id), rule) and "invalid" not in str(r.rule_id)
    ]
    if not matching:
        raise ToolInputError(
            f"no rule {rule!r} in the reference; give a marker it declares "
            "or a rule id prefix"
        )
    markers = {str(r.rule_id).split("/")[1] for r in matching}
    libraries: dict[str, list[str]] = {}
    for r in matching:
        if str(r.rule_id).split("/")[1] not in _FORBIDDING:
            continue
        holder = state.source_by_id.get(r.selector.source_entity_id)
        if holder is None:
            continue
        forbidden = {str(name) for name in r.params.get("forbidden") or []}
        key = str(holder.filepath_rel)
        libraries[key] = sorted(set(libraries.get(key, [])) | forbidden)
    if all(r.evidence_type == "runtime" for r in matching):
        markers.add(_RUNTIME_ONLY)
    # A marker with a static part is about the entity it is declared on; its
    # runtime part may be anchored elsewhere (the entry it runs).
    static_markers = {
        str(r.rule_id).split("/")[1] for r in matching if r.evidence_type != "runtime"
    }
    files: Optional[set[str]] = set()
    for r in matching:
        if r.evidence_type == "runtime" and str(r.rule_id).split("/")[1] in (
            static_markers
        ):
            continue
        entity = state.source_by_id.get(r.selector.source_entity_id)
        if entity is None:
            continue
        if entity.kind == "module" and not entity.module_path:
            files = None
            break
        assert files is not None  # nosec B101 - narrowed above
        files.add(str(entity.filepath_rel))
    if not markers - {_RUNTIME_ONLY} <= set(_FORBIDDING):
        libraries = {}
    aims = (
        _delegations(source_path, state, matching)
        if markers - {_RUNTIME_ONLY} == {"require_runtime_delegation"}
        else set()
    )
    if markers - {_RUNTIME_ONLY} == {"forbid_foreign_writes"}:
        # Writes are watched only in the methods (or classes) the marker is
        # on: a method without it may write as it likes.
        aims = {
            ("", str(entity.qualname), "")
            for r in matching
            if (entity := state.source_by_id.get(r.selector.source_entity_id))
            is not None
        }
    # ``aims``: what the mutants must be about — ``(class, constructor
    # parameter, member)`` for a delegation marker, ``("", qualname, "")``
    # of the marked entities for forbid_foreign_writes; empty: no narrowing.
    return markers, files, libraries, aims


_FORBIDDING = ("forbid_imports", "forbid_runtime_imports")


def _own_modules(source_path: Path) -> set[str]:
    """Top-level module and package names of the project at ``source_path``."""
    return {
        path.stem if path.is_file() else path.name
        for path in source_path.iterdir()
        if (path.suffix == ".py" and path.stem != "__init__")
        or (path.is_dir() and (path / "__init__.py").is_file())
    }


def verify_marker(
    source: str,
    rule: str,
    operators: Optional[list[str]] = None,
    files: Optional[list[str]] = None,
    libraries: Optional[list[str]] = None,
    max_mutants: int = DEFAULT_MAX_MUTANTS,
    dynamic: bool = False,
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
    detail: str = "problems",
) -> dict[str, Any]:
    """Check that the reference's ``rule`` catches seeded architectural violations.

    The named ``operators`` (all by default) seed violations into copies of
    the reference; each copy, and an unchanged one, is evaluated against the
    reference. ``rule`` is a marker name (``"forbid_imports"``) or a rule id
    prefix (``"DEP001"``). A mutant is *killed* when the rule fails on it
    with a violation, *survives* when it passes, and *did not run* when a
    runtime rule could not observe it. The marker is accepted when it passes
    on the unchanged reference and no mutant survives.

    Without ``operators`` only the operators the marker can see are used;
    without ``files`` only the files of the entities the marker is declared
    on (every file for a marker on the root package). Only the rules ``rule``
    names are evaluated. ``detail="problems"`` lists the survivors and the
    mutants that did not run (killed ones are counted per operator);
    ``detail="all"`` lists every mutant.
    """
    import shutil
    import tempfile

    from pythonarchtesting.mutation.operators import (
        DEFAULT_LIBRARIES,
        generate_mutants,
    )
    from pythonarchtesting.runner import run_projects

    source_path = require_absolute(source, "source")
    if not source_path.is_dir():
        raise ToolInputError(f"source does not exist: {source}")
    _not_a_task(source_path, "verify_marker")
    if not _in_range(max_mutants, 1, 200) or int(max_mutants) != max_mutants:
        raise ToolInputError("max_mutants must be a whole number in [1, 200]")
    if detail not in _DETAILS:
        raise ToolInputError(f"detail must be one of {', '.join(_DETAILS)}: {detail}")
    markers, marker_files, forbidden_by_file, aims = _scope(source_path, rule, config)
    own_modules = _own_modules(source_path)
    forbidden_libraries = sorted(
        {
            name
            for names in forbidden_by_file.values()
            for name in names
            if name.split(".")[0] not in own_modules
        }
    )
    runtime_only = _RUNTIME_ONLY in markers
    markers.discard(_RUNTIME_ONLY)
    chosen_by_marker = operators is None
    if operators is None:
        operators = sorted(
            {op for marker in markers for op in _OPERATORS_BY_MARKER.get(marker, ())}
        )
        if not operators:
            raise ToolInputError(
                f"no operator seeds a violation {', '.join(sorted(markers))} can see; "
                "give operators explicitly"
            )
    if runtime_only and not dynamic:
        raise ToolInputError(
            f"{', '.join(sorted(markers))} is checked only at run time: "
            "call verify_marker with dynamic=True"
        )
    chosen_libraries = tuple(libraries or forbidden_libraries or DEFAULT_LIBRARIES)
    skipped: list[tuple[str, str]] = []
    try:
        mutants = generate_mutants(
            source_path,
            operators,
            libraries=chosen_libraries,
            skipped=skipped,
        )
    except ValueError as exc:
        raise ToolInputError(str(exc)) from exc
    if files is not None:
        if not isinstance(files, list):
            raise ToolInputError("files must be a list of paths relative to source")
        wanted: Optional[set[str]] = {str(name).removeprefix("./") for name in files}
    else:
        wanted = marker_files
    if wanted is not None:
        # A mutant counts for the files whose markers it is about (another
        # module reaching past a module's interface counts for that module).
        mutants = [mutant for mutant in mutants if mutant.subject in wanted]
    if chosen_by_marker and not libraries and forbidden_by_file:
        # An import mutant only of what a marker of that file forbids
        # (operators and libraries given explicitly are taken as asked).
        mutants = [
            mutant
            for mutant in mutants
            if not mutant.imported
            or any(
                mutant.imported == name or mutant.imported.startswith(f"{name}.")
                for name in forbidden_by_file.get(mutant.file, [])
            )
        ]
    if chosen_by_marker and aims and markers == {"forbid_foreign_writes"}:
        mutants = [
            mutant
            for mutant in mutants
            if any(
                mutant.function == where or mutant.function.startswith(f"{where}.")
                for _, where, _ in aims
            )
        ]
    elif chosen_by_marker and aims:
        # A delegation marker is about one collaborator: cutting out calls to
        # the others is no violation of it.
        mutants = [
            mutant
            for mutant in mutants
            if any(
                mutant.owner == owner
                and mutant.collaborator == parameter
                and (not member or mutant.member == member)
                for owner, parameter, member in aims
            )
        ]
    if not mutants:
        raise ToolInputError(
            "no mutants: the operators found nothing to change in the files given"
            + "".join(f"; {file} was not read ({why})" for file, why in skipped)
        )
    total_generated = len(mutants)
    mutants = _sample(mutants, int(max_mutants))
    truncated = total_generated > len(mutants)
    policy = _sandbox_policy(dynamic, sandbox, sandbox_memory_mb)
    try:
        loaded, applied = resolve_config(source_path, config)
    except (ConfigurationError, OSError) as exc:
        raise ToolInputError(str(exc)) from exc

    ignore = shutil.ignore_patterns("__pycache__", ".*")
    with tempfile.TemporaryDirectory(prefix="pat-verify-") as tmp:
        workdir = Path(tmp)
        baseline = workdir / "reference" / source_path.name
        shutil.copytree(source_path, baseline, ignore=ignore)
        paths = {}
        for mutant in mutants:
            copy = workdir / mutant.id / source_path.name
            shutil.copytree(source_path, copy, ignore=ignore)
            (copy / mutant.file).write_text(mutant.source, encoding="utf-8")
            for other, text in mutant.also:
                (copy / other).write_text(text, encoding="utf-8")
            paths[mutant.id] = copy
        try:
            _, states = run_projects(
                config=loaded,
                source_path=str(source_path),
                targets=[str(baseline), *(str(path) for path in paths.values())],
                load_config_first=False,
                dynamic=dynamic,
                sandbox=policy,
                rule_filter=lambda candidate: _rule_matches(
                    str(candidate.rule_id), rule
                ),
            )
        except (ConfigurationError, OSError) as exc:
            raise ToolInputError(str(exc)) from exc
        by_path = {Path(state.target_path).resolve(): state for state in states}
        base_results = list(by_path[baseline.resolve()].rule_results)
        if not any(_rule_matches(str(r.rule_id), rule) for r in base_results):
            raise ToolInputError(
                f"no rule {rule!r} in the reference; give a marker it declares "
                "or a rule id prefix"
            )
        base_outcome, base_failing, base_why = _judge(base_results, rule)
        gaps = _case_gaps(base_results, rule)
        reported = []
        for mutant in mutants:
            state = by_path[paths[mutant.id].resolve()]
            outcome, failing, why = _judge(list(state.rule_results), rule)
            entry: dict[str, Any] = {
                "id": mutant.id,
                "operator": mutant.operator,
                "file": mutant.file,
                "description": mutant.description,
                "outcome": outcome,
                "failing": failing,
                "why": why,
            }
            if outcome == "survived" and any(
                mutant.line in gap["lines"] and mutant.file == gap["file"]
                for gap in gaps
            ):
                entry["unexercised"] = True
                entry["why"] = [
                    f"no case of the marker runs line {mutant.line} of {mutant.file}"
                ]
            reported.append(entry)
    counts = {
        key: sum(1 for m in reported if m["outcome"] == key)
        for key in ("killed", "survived", "not_run")
    }
    reference_passes = base_outcome == "survived"
    return {
        "rule": rule,
        "config": applied,
        "dynamic": dynamic,
        "reference_passes": reference_passes,
        "reference_failing": base_failing if not reference_passes else [],
        "reference_why": base_why if not reference_passes else [],
        # Not every mutant was tried when the sample was cut: no acceptance.
        "accepted": reference_passes
        and counts["survived"] == 0
        and counts["not_run"] == 0
        and not truncated,
        "total": len(reported),
        "generated": total_generated,
        "truncated": truncated,
        **counts,
        "scope": {
            "markers": sorted(markers),
            "operators": sorted(set(operators)),
            "files": sorted(wanted) if wanted is not None else "all",
            **(
                {
                    "libraries": sorted(
                        {
                            m.imported
                            for m in mutants
                            if m.operator in ("add_library", "dynamic_import")
                        }
                    )
                }
                if {"add_library", "dynamic_import"} & set(operators)
                else {}
            ),
        },
        "by_operator": _by_operator(reported),
        # Files the operators could not read (no mutant was made in them).
        **(
            {"skipped_files": [{"file": f, "why": w} for f, w in skipped]}
            if skipped
            else {}
        ),
        "hints": _hints(reported, gaps),
        "case_gaps": [
            {"rule": gap["rule"], "file": gap["file"], "lines": _ranges(gap["lines"])}
            for gap in gaps
        ],
        "mutants": (
            reported
            if detail == "all"
            else [m for m in reported if m["outcome"] != "killed"]
        ),
    }


def _case_gaps(results: list[Any], rule: str) -> list[dict[str, Any]]:
    """Lines of each runtime part's code that no case of the marker ran on the
    reference: a violation there cannot be seen."""
    gaps = []
    for result in results:
        if not _rule_matches(str(result.rule_id), rule):
            continue
        coverage = (result.details or {}).get("coverage") or {}
        lines = list(coverage.get("unexercised_lines") or [])
        if lines and coverage.get("file"):
            gaps.append(
                {"rule": str(result.rule_id), "file": coverage["file"], "lines": lines}
            )
    return gaps


def _ranges(lines: list[int]) -> str:
    from pythonarchtesting.execution.evaluators.runtime_structure import _line_ranges

    return _line_ranges(lines)


def _hints(reported: list[dict[str, Any]], gaps: list[dict[str, Any]]) -> list[str]:
    """What the survivors call for, beyond the marker's own arguments."""
    hints = []
    survived = {m["operator"] for m in reported if m["outcome"] == "survived"}
    if "dynamic_import" in survived:
        hints.append(
            "an import by a computed name inside a function survives: no static "
            "rule sees it and forbid_runtime_imports sees only what importing the "
            "module runs; forbid the library's use with forbid_runtime_calls on "
            "the functions that could load it"
        )
    if gaps:
        hints.append(
            "the marker's cases leave lines unrun (case_gaps): a violation there "
            "goes unseen; add cases for them and check them with check_cases"
        )
    return hints


def _by_operator(reported: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Killed, survived and not-run mutants per operator."""
    summary: dict[str, dict[str, int]] = {}
    for mutant in reported:
        counts = summary.setdefault(
            mutant["operator"], {"killed": 0, "survived": 0, "not_run": 0}
        )
        counts[mutant["outcome"]] += 1
    return summary


__all__ = [
    "DEFAULT_MAX_MUTANTS",
    "DEFAULT_MIN_COVERAGE",
    "check_cases",
    "verify_marker",
]
