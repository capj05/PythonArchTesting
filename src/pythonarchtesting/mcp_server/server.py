from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Optional

import anyio
import anyio.from_thread
import anyio.to_thread

# Imported under their own names before the module-level ``mcp`` server instance below.
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from pythonarchtesting.mcp_server import evaluation, markers, reports
from pythonarchtesting.mcp_server.errors import ToolInputError

INSTRUCTIONS = """\
Authoring and checking architectural markers for PythonArchTesting.
1. Look up markers with list_markers / describe_marker.
2. Edit the reference files with your own file tools; this server never edits files.
3. After every marker change, run validate_declarations.
4. Verify a marker with run_evaluation on the reference as the only target (it must
   pass) and on a copy you deliberately broke (it must fail).
5. Evaluate a batch of submissions with targets_dir.
6. Read results through summarize_report, then explain_target / explain_rule.
7. A rule that fails almost every submission suggests a wrong marker, not wrong students.
8. All paths must be absolute.
9. dynamic=True runs student code, under bwrap by default.
"""

mcp = MCPServer("pythonarchtesting", instructions=INSTRUCTIONS)

# Every tool but run_evaluation only reads; openWorldHint=False marks the inputs as local.
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
) -> dict[str, Any]:
    """Evaluate student projects against the reference at ``source`` and write JSON and
    Markdown reports into a new run directory under ``output_dir`` (all paths absolute).
    Give either ``targets`` (project directories) or ``targets_dir`` (a directory of
    projects, optionally narrowed by ``project_pattern`` / ``exclude_patterns``).
    Returns a summary and ``report_json``; read details with summarize_report.
    ``dynamic=True`` runs student code and needs a sandbox (``bwrap`` by default;
    ``limits`` is weaker; an unavailable sandbox is an error). Writes only into the
    run directory."""

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
