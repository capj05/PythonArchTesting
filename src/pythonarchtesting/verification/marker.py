"""Check that a reference's marker catches seeded architectural violations.

The named operators (by default those the marker can see) seed violations
into copies of the reference; each copy, and an unchanged one, is evaluated
against the reference, by the rules the marker names only. A mutant is
*killed* when the rule fails on it with a violation, *survives* when it
passes, and *did not run* when a runtime rule could not observe it
(``verification.mutant_runs``). The marker is accepted when it passes on the
unchanged reference and no mutant survives or did not run, and every mutant
was tried.

What cannot be checked as asked raises ``InvalidInputError`` with the reason.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.exceptions import ConfigurationError
from pythonarchtesting.invalid_input import InvalidInputError
from pythonarchtesting.runner.settings import resolve_config, sandbox_policy
from pythonarchtesting.verification.mutant_runs import (
    copy_reference,
    mutant_outcome,
    rule_matches,
    sample_by_operator,
    write_mutants,
)

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
_RUNTIME_ONLY = "<runtime only>"
_FORBIDDING = ("forbid_imports", "forbid_runtime_imports")


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
        raise InvalidInputError(str(exc)) from exc
    matching = [
        r
        for r in state.rules
        if rule_matches(str(r.rule_id), rule) and "invalid" not in str(r.rule_id)
    ]
    if not matching:
        raise InvalidInputError(
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


def _own_modules(source_path: Path) -> set[str]:
    """Top-level module and package names of the project at ``source_path``."""
    return {
        path.stem if path.is_file() else path.name
        for path in source_path.iterdir()
        if (path.suffix == ".py" and path.stem != "__init__")
        or (path.is_dir() and (path / "__init__.py").is_file())
    }


def _operators(
    markers: set[str],
    operators: Optional[list[str]],
    runtime_only: bool,
    dynamic: bool,
) -> list[str]:
    """``operators``, or without them those that seed a violation the
    ``markers`` can see; a marker checked only at run time needs ``dynamic``."""
    if operators is None:
        operators = sorted(
            {op for marker in markers for op in _OPERATORS_BY_MARKER.get(marker, ())}
        )
        if not operators:
            raise InvalidInputError(
                f"no operator seeds a violation {', '.join(sorted(markers))} can see; "
                "give operators explicitly"
            )
    if runtime_only and not dynamic:
        raise InvalidInputError(
            f"{', '.join(sorted(markers))} is checked only at run time: "
            "call verify_marker with dynamic=True"
        )
    return operators


def _wanted_files(
    files: Optional[list[str]], marker_files: Optional[set[str]]
) -> Optional[set[str]]:
    """The files a mutant must be about: ``files`` (relative to the
    reference), or without them those of the marker; ``None``: every file."""
    if files is None:
        return marker_files
    if not isinstance(files, list):
        raise InvalidInputError("files must be a list of paths relative to source")
    return {str(name).removeprefix("./") for name in files}


def _narrow(
    mutants: list[Any],
    wanted: Optional[set[str]],
    forbidden_by_file: dict[str, list[str]],
    aims: set[tuple[str, str, str]],
    markers: set[str],
) -> list[Any]:
    """The ``mutants`` that are about what the marker states: of the
    ``wanted`` files, importing only what a marker of their file forbids
    (``forbidden_by_file``, empty: anything), and about the ``aims`` of the
    marker (``_scope``; empty: anything)."""
    if wanted is not None:
        # A mutant counts for the files whose markers it is about (another
        # module reaching past a module's interface counts for that module).
        mutants = [mutant for mutant in mutants if mutant.subject in wanted]
    if forbidden_by_file:
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
    if aims and markers == {"forbid_foreign_writes"}:
        mutants = [
            mutant
            for mutant in mutants
            if any(
                mutant.function == where or mutant.function.startswith(f"{where}.")
                for _, where, _ in aims
            )
        ]
    elif aims:
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
    return mutants


def _run(
    source_path: Path,
    mutants: list[Any],
    loaded: Any,
    rule: str,
    dynamic: bool,
    policy: Any,
) -> tuple[list[Any], dict[str, list[Any]]]:
    """The results of ``rule`` on an unchanged copy of the reference and on
    each mutant's copy (by mutant id)."""
    from pythonarchtesting.runner import run_projects

    with tempfile.TemporaryDirectory(prefix="pat-verify-") as tmp:
        workdir = Path(tmp)
        baseline = workdir / "reference" / source_path.name
        copy_reference(source_path, baseline)
        paths = write_mutants(source_path, workdir, mutants)
        try:
            _, states = run_projects(
                config=loaded,
                source_path=str(source_path),
                targets=[str(baseline), *(str(path) for path in paths.values())],
                load_config_first=False,
                dynamic=dynamic,
                sandbox=policy,
                rule_filter=lambda candidate: rule_matches(
                    str(candidate.rule_id), rule
                ),
            )
        except (ConfigurationError, OSError) as exc:
            raise InvalidInputError(str(exc)) from exc
        by_path = {Path(state.target_path).resolve(): state for state in states}
        return list(by_path[baseline.resolve()].rule_results), {
            mutant.id: list(by_path[paths[mutant.id].resolve()].rule_results)
            for mutant in mutants
        }


def _mutant_entry(
    mutant: Any, results: list[Any], rule: str, gaps: list[dict[str, Any]]
) -> dict[str, Any]:
    """One mutant's outcome; a survivor on a line no case of the marker runs
    is ``unexercised``."""
    outcome, failing, why = mutant_outcome(results, rule)
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
        mutant.line in gap["lines"] and mutant.file == gap["file"] for gap in gaps
    ):
        entry["unexercised"] = True
        entry["why"] = [
            f"no case of the marker runs line {mutant.line} of {mutant.file}"
        ]
    return entry


def verify_marker(
    source_path: Path,
    rule: str,
    operators: Optional[list[str]],
    files: Optional[list[str]],
    libraries: Optional[list[str]],
    max_mutants: int,
    dynamic: bool,
    sandbox: Optional[str],
    sandbox_memory_mb: int,
    config: Optional[str],
) -> dict[str, Any]:
    """Check that the reference's ``rule`` catches seeded violations (module
    docstring); ``rule`` is a marker name (``"forbid_imports"``) or a rule id
    prefix (``"DEP001"``).

    Without ``operators`` only the operators the marker can see are used;
    without ``files`` only the files of the entities the marker is declared
    on (every file for a marker on the root package). ``mutants`` lists
    every mutant tried, killed ones too."""
    markers, marker_files, forbidden_by_file, aims = _scope(source_path, rule, config)
    forbidden_libraries = _forbidden_libraries(source_path, forbidden_by_file)
    runtime_only = _RUNTIME_ONLY in markers
    markers.discard(_RUNTIME_ONLY)
    chosen_by_marker = operators is None
    operators = _operators(markers, operators, runtime_only, dynamic)
    skipped: list[tuple[str, str]] = []
    mutants = _generate(
        source_path, operators, libraries or forbidden_libraries, skipped
    )
    wanted = _wanted_files(files, marker_files)
    mutants = _narrow(
        mutants,
        wanted,
        forbidden_by_file if chosen_by_marker and not libraries else {},
        aims if chosen_by_marker else set(),
        markers,
    )
    if not mutants:
        raise InvalidInputError(
            "no mutants: the operators found nothing to change in the files given"
            + "".join(f"; {file} was not read ({why})" for file, why in skipped)
        )
    total_generated = len(mutants)
    mutants = sample_by_operator(mutants, int(max_mutants))
    policy = sandbox_policy(dynamic, sandbox, sandbox_memory_mb)
    loaded, applied = _resolve_config(source_path, config)
    base_results, results = _run(source_path, mutants, loaded, rule, dynamic, policy)
    if not any(rule_matches(str(r.rule_id), rule) for r in base_results):
        raise InvalidInputError(
            f"no rule {rule!r} in the reference; give a marker it declares "
            "or a rule id prefix"
        )
    gaps = _case_gaps(base_results, rule)
    reported = [_mutant_entry(m, results[m.id], rule, gaps) for m in mutants]
    return {
        "rule": rule,
        "config": applied,
        "dynamic": dynamic,
        **_verdict(base_results, rule, reported, total_generated),
        "scope": _scope_report(markers, operators, wanted, mutants),
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
        "mutants": reported,
    }


def _forbidden_libraries(
    source_path: Path, forbidden_by_file: dict[str, Any]
) -> list[str]:
    """The libraries outside the reference that the marker forbids: an
    ``add_library`` mutant imports one of them, not a default library."""
    own_modules = _own_modules(source_path)
    return sorted(
        {
            name
            for names in forbidden_by_file.values()
            for name in names
            if name.split(".")[0] not in own_modules
        }
    )


def _generate(
    source_path: Path,
    operators: list[str],
    libraries: list[str],
    skipped: list[tuple[str, str]],
) -> list[Any]:
    """Every mutant the ``operators`` make in the reference, with the
    ``libraries`` given (the default ones when none is); the files that could
    not be read are added to ``skipped``. An operator that cannot be applied
    is invalid input."""
    from pythonarchtesting.mutation.operators import (
        DEFAULT_LIBRARIES,
        generate_mutants,
    )

    try:
        return generate_mutants(
            source_path,
            operators,
            libraries=tuple(libraries or DEFAULT_LIBRARIES),
            skipped=skipped,
        )
    except ValueError as exc:
        raise InvalidInputError(str(exc)) from exc


def _resolve_config(source_path: Path, config: Optional[str]) -> tuple[Any, Any]:
    """The loaded configuration the rules run with and the file it came from;
    a configuration that cannot be read is invalid input."""
    try:
        return resolve_config(source_path, config)
    except (ConfigurationError, OSError) as exc:
        raise InvalidInputError(str(exc)) from exc


def _verdict(
    base_results: list[Any],
    rule: str,
    reported: list[dict[str, Any]],
    total_generated: int,
) -> dict[str, Any]:
    """Whether the reference passes, whether the marker is accepted, and the
    mutant counts behind it. A sample cut short (``truncated``) is never
    accepted: not every mutant was tried."""
    base_outcome, base_failing, base_why = mutant_outcome(base_results, rule)
    counts = {
        key: sum(1 for m in reported if m["outcome"] == key)
        for key in ("killed", "survived", "not_run")
    }
    truncated = total_generated > len(reported)
    reference_passes = base_outcome == "survived"
    return {
        "reference_passes": reference_passes,
        "reference_failing": base_failing if not reference_passes else [],
        "reference_why": base_why if not reference_passes else [],
        "accepted": reference_passes
        and counts["survived"] == 0
        and counts["not_run"] == 0
        and not truncated,
        "total": len(reported),
        "generated": total_generated,
        "truncated": truncated,
        **counts,
    }


def _scope_report(
    markers: set[str],
    operators: list[str],
    wanted: Optional[set[str]],
    mutants: list[Any],
) -> dict[str, Any]:
    """What the run covered: the markers, the operators, the files, and the
    libraries the library operators imported when one of them ran."""
    return {
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
    }


def _case_gaps(results: list[Any], rule: str) -> list[dict[str, Any]]:
    """Lines of each runtime part's code that no case of the marker ran on the
    reference: a violation there cannot be seen."""
    gaps = []
    for result in results:
        if not rule_matches(str(result.rule_id), rule):
            continue
        coverage = (result.details or {}).get("coverage") or {}
        lines = list(coverage.get("unexercised_lines") or [])
        if lines and coverage.get("file"):
            gaps.append(
                {"rule": str(result.rule_id), "file": coverage["file"], "lines": lines}
            )
    return gaps


def _ranges(lines: list[int]) -> str:
    from pythonarchtesting.execution.evaluators.runtime_structure import line_ranges

    return line_ranges(lines)


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


__all__ = ["verify_marker"]
