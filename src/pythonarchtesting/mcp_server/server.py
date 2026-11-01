from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal, Optional

import anyio
import anyio.from_thread
import anyio.to_thread

# Imported under their own names before the module-level ``mcp`` server instance below.
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from pythonarchtesting.mcp_server import authoring, evaluation, markers, reports
from pythonarchtesting.mcp_server.errors import ToolInputError

INSTRUCTIONS = """\
Authoring and checking architectural markers for PythonArchTesting.
1. Look up markers with list_markers / describe_marker.
2. Edit the reference files with your own file tools; this server never edits files.
3. After every marker change, run validate_declarations.
4. Verify a marker with verify_marker (seeded violations must fail it, the reference
   must pass); check runtime cases with check_cases before using them.
5. Evaluate a batch of submissions with targets_dir.
6. Read results through summarize_report, then explain_target / explain_rule;
   unpaired entities: propose_mapping, then run_evaluation(mapping=...).
7. A rule that fails almost every submission suggests a wrong marker, not wrong students.
8. All paths must be absolute.
9. dynamic=True runs student code, under bwrap by default.
"""

mcp = MCPServer("pythonarchtesting", instructions=INSTRUCTIONS)

# Tools that run reference or target code (run_evaluation, check_cases,
# verify_marker, check_architecture) are EVALUATE; every other tool only reads.
# openWorldHint=False marks the inputs as local.
READONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)
EVALUATE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=False,
)


@contextmanager
def _tool_errors() -> Iterator[None]:
    """Let a ToolInputError message reach the client.

    The SDK hides the message of any exception that is not a ToolError.
    """
    try:
        yield
    except ToolInputError as error:
        raise ToolError(str(error)) from error


@mcp.tool(annotations=READONLY)
def list_markers(category: Optional[str] = None) -> list[dict[str, Any]]:
    """List the available markers with category, one-line summary and whether they
    need dynamic=True. Use first, to find the marker that expresses a rule.
    ``category`` filters, case-insensitively."""
    with _tool_errors():
        return markers.list_markers(category)


@mcp.tool(annotations=READONLY)
def describe_marker(name: str) -> dict[str, Any]:
    """Return the full documentation of one marker: arguments, examples, pitfalls.
    Use before adding the marker to a reference file."""
    with _tool_errors():
        return markers.describe_marker(name)


@mcp.tool(annotations=READONLY)
def validate_declarations(
    source: str,
    reference_modules: Optional[list[str]] = None,
    validation_scope: str = "all",
    config: Optional[str] = None,
) -> dict[str, Any]:
    """Check the marker declarations of the reference project at ``source`` (absolute
    path) without running any target code. Use after every marker change; fix every
    reported problem before evaluating."""
    with _tool_errors():
        return evaluation.validate_declarations_tool(
            source, reference_modules, validation_scope, config
        )


@mcp.tool(annotations=EVALUATE)
async def run_evaluation(
    ctx: Context,
    source: str,
    output_dir: str,
    targets: Optional[list[str]] = None,
    targets_dir: Optional[str] = None,
    project_pattern: Optional[str] = None,
    exclude_patterns: Optional[list[str]] = None,
    reference_modules: Optional[list[str]] = None,
    validation_scope: str = "all",
    dynamic: bool = False,
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = evaluation.DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
    architecture: bool = False,
    mapping: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Evaluate student projects against the reference at ``source`` and write JSON and
    Markdown reports into a new run directory under ``output_dir`` (all paths absolute).
    Give either ``targets`` (project directories) or ``targets_dir`` (a directory of
    projects, optionally narrowed by ``project_pattern`` / ``exclude_patterns``).
    Returns a summary and ``report_json``; read details with summarize_report.
    ``dynamic=True`` runs student code and needs a sandbox (``bwrap`` by default;
    ``limits`` is weaker; an unavailable sandbox is an error). ``architecture=True``
    compares every target with the reference's module dependencies even without an
    architecture_entry marker. ``mapping`` (from propose_mapping) pairs entities the
    matching could not; each pair is checked first. Writes only into the run
    directory."""

    def on_progress(done: int, total: int, target_id: str) -> None:
        anyio.from_thread.run(
            ctx.report_progress, done, total, f"evaluated {target_id}"
        )

    def run() -> dict[str, Any]:
        return evaluation.run_evaluation(
            source,
            output_dir,
            targets=targets,
            targets_dir=targets_dir,
            project_pattern=project_pattern,
            exclude_patterns=exclude_patterns,
            reference_modules=reference_modules,
            validation_scope=validation_scope,
            dynamic=dynamic,
            sandbox=sandbox,
            sandbox_memory_mb=sandbox_memory_mb,
            config=config,
            on_progress=on_progress,
            architecture=architecture,
            mapping=mapping,
        )

    with _tool_errors():
        return await anyio.to_thread.run_sync(run)


@mcp.tool(annotations=EVALUATE)
async def check_cases(
    source: str,
    entry: str,
    cases: list[dict[str, Any]],
    init: Optional[dict[str, Any]] = None,
    min_coverage: float = authoring.DEFAULT_MIN_COVERAGE,
    timeout_s: float = 5.0,
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = evaluation.DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
) -> dict[str, Any]:
    """Run proposed ``cases`` of the reference function ``entry`` ("module.function")
    on the reference at ``source`` (absolute) before putting them into a runtime
    marker or architecture_entry. ``accepted`` is true when every case runs and the
    cases cover at least ``min_coverage`` of the entry's lines; ``reasons`` and
    ``coverage.unexercised_lines`` say what to add. Runs the reference sandboxed."""

    def run() -> dict[str, Any]:
        return authoring.check_cases(
            source,
            entry,
            cases,
            init=init,
            min_coverage=min_coverage,
            timeout_s=timeout_s,
            sandbox=sandbox,
            sandbox_memory_mb=sandbox_memory_mb,
            config=config,
        )

    with _tool_errors():
        return await anyio.to_thread.run_sync(run)


@mcp.tool(annotations=EVALUATE)
async def verify_marker(
    source: str,
    rule: str,
    operators: Optional[list[str]] = None,
    files: Optional[list[str]] = None,
    libraries: Optional[list[str]] = None,
    max_mutants: int = authoring.DEFAULT_MAX_MUTANTS,
    dynamic: bool = False,
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = evaluation.DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
    detail: Literal["problems", "all"] = "problems",
) -> dict[str, Any]:
    """Check a marker of the reference at ``source`` (absolute) against seeded
    violations. Named operators (add_import, lazy_import, add_library,
    dynamic_import, rebuild_injected, drop_call, use_private_name, break_port)
    mutate copies of the reference; ``rule`` (marker name
    or rule id prefix) must fail on each mutant (killed) and pass on the reference.
    Without operators/files, only the operators the marker can see and the files it is
    declared on are used (``scope`` says which); only the rules named are evaluated.
    ``by_operator`` counts the outcomes; ``mutants`` lists survivors and mutants that
    did not run (``detail="all"``: every mutant). A survivor is a gap in the marker or
    a change the architecture allows; ``hints`` says what survivors call for and
    ``case_gaps`` the lines no case of the marker ran. Runtime markers need
    dynamic=True."""

    def run() -> dict[str, Any]:
        return authoring.verify_marker(
            source,
            rule,
            operators=operators,
            files=files,
            libraries=libraries,
            max_mutants=max_mutants,
            dynamic=dynamic,
            sandbox=sandbox,
            sandbox_memory_mb=sandbox_memory_mb,
            config=config,
            detail=detail,
        )

    with _tool_errors():
        return await anyio.to_thread.run_sync(run)


@mcp.tool(annotations=EVALUATE)
async def check_architecture(
    source: str,
    target: str,
    mode: Literal["static", "full"] = "static",
    mapping: Optional[dict[str, Any]] = None,
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = evaluation.DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
) -> dict[str, Any]:
    """Check one project (``target``, absolute) against the reference at ``source``
    and return the verdict directly: ``passed``, the problems with structured
    feedback (edge, file, line, what the reference does) and undecided changes.
    For an agent fixing code in a loop; writes nothing. ``passed`` holds for what ran:
    ``complete`` is false when a part was SKIPPED (runtime checks in static mode).
    ``mode="full"`` also runs the code (sandboxed; ``sandbox`` and
    ``sandbox_memory_mb`` apply only then) and compares calls, created objects and
    libraries. ``mapping`` pairs renamed entities (see propose_mapping); the result
    lists the pairs applied and refused."""

    def run() -> dict[str, Any]:
        return evaluation.check_architecture(
            source,
            target,
            mode=mode,
            mapping=mapping,
            sandbox=sandbox,
            sandbox_memory_mb=sandbox_memory_mb,
            config=config,
        )

    with _tool_errors():
        return await anyio.to_thread.run_sync(run)


@mcp.tool(annotations=EVALUATE)
async def describe_architecture(
    source: str,
    mode: Literal["static", "full"] = "static",
    sandbox: Optional[str] = None,
    sandbox_memory_mb: int = evaluation.DEFAULT_SANDBOX_MEMORY_MB,
    config: Optional[str] = None,
) -> dict[str, Any]:
    """The architecture model of the reference at ``source`` (absolute): what
    architecture_entry compares a target with. Its modules, the imports between
    them with the line of each, the libraries each module imports, and the
    architecture_entry declaration (policy, allow/forbid, ignored libraries).
    ``mode="full"`` also runs the declared cases on the reference, sandboxed, and
    adds the calls between modules, which module creates objects of which class,
    and the libraries called. Edges are written as exceptions take them
    ("a -> b"; the package itself is "__init__"). Describes only, judges nothing."""

    def run() -> dict[str, Any]:
        return authoring.describe_architecture(
            source,
            mode=mode,
            sandbox=sandbox,
            sandbox_memory_mb=sandbox_memory_mb,
            config=config,
        )

    with _tool_errors():
        return await anyio.to_thread.run_sync(run)


@mcp.tool(annotations=READONLY)
def summarize_report(
    report_path: str, offset: int = 0, limit: int = 50
) -> dict[str, Any]:
    """Summarise a saved report.json (absolute path): totals, most-failed rules and a
    page of targets. Start here when reading results; page with offset/limit."""
    with _tool_errors():
        return reports.summarize_report(report_path, offset, limit)


@mcp.tool(annotations=READONLY)
def propose_mapping(report_path: str, target: str) -> dict[str, Any]:
    """List the reference entities one target left unpaired (``required_target_missing``
    results come from them), each with its best candidates in the target. Propose
    pairs from it, then rerun run_evaluation with mapping={"pairs": {...}}; module
    pairs ("controller": "handler") pair their entities by name."""
    with _tool_errors():
        return reports.propose_mapping(report_path, target)


@mcp.tool(annotations=READONLY)
def explain_target(
    report_path: str,
    target: str,
    include_passed: bool = False,
    offset: int = 0,
    limit: int = 20,
) -> dict[str, Any]:
    """Explain why one target failed: its problem results with evidence. Use after
    summarize_report to inspect a single submission."""
    with _tool_errors():
        return reports.explain_target(
            report_path, target, include_passed, offset, limit
        )


@mcp.tool(annotations=READONLY)
def explain_rule(
    report_path: str, rule: str, offset: int = 0, limit: int = 50
) -> dict[str, Any]:
    """Show how one rule fared across all targets. Use to judge whether a rule is
    wrong (fails almost everywhere) or genuinely discriminating."""
    with _tool_errors():
        return reports.explain_rule(report_path, rule, offset, limit)


def main() -> None:
    mcp.run()
