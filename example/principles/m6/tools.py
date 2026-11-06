"""Command-line access to the teaching tools for the M6 agents.

The agents of the M6 evaluation cannot reach the MCP server, so this script
gives them the functions behind its tools from a shell, printing compact JSON
(one line):

- ``describe PRINCIPLE``: the MCP ``describe_principle``;
- ``describe_marker NAME``: the MCP ``describe_marker`` (the case language of
  the runtime markers, which a task's ``[cases]`` use);
- ``prepare TASK_DIR``: the MCP ``prepare_task`` (sandbox ``bwrap``);
- ``evaluate TASK_DIR TARGETS_DIR [--out DIR]``: the MCP ``run_evaluation``
  with a dynamic run (the task's principle), then ``class_overview`` of the
  report; ``report_json`` says where the report is (under ``--out``, by default
  ``data/reports/`` next to this file);
- ``explain REPORT TARGET PRINCIPLE``: the MCP ``explain_target`` with
  ``principle``.

Relative paths are resolved against the current directory. An input the tool
refuses prints ``{"error": ...}`` and exits 2. The pattern is
``example/llm_authoring/tools.py``.

Usage::

    python example/principles/m6/tools.py prepare /abs/path/task
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPORTS = HERE / "data" / "reports"


def _abs(path: str) -> str:
    return str(Path(path).resolve())


def evaluate(task_dir: str, targets_dir: str, out: str) -> dict[str, Any]:
    """Evaluate every submission of ``targets_dir`` against the task and give
    the class overview by the task's principle."""
    from pythonarchtesting.mcp_server import evaluation, reports

    Path(out).mkdir(parents=True, exist_ok=True)
    run = evaluation.run_evaluation(
        _abs(task_dir), _abs(out), targets_dir=_abs(targets_dir), dynamic=True
    )
    overview = reports.class_overview(run["report_json"])
    return {"report_json": run["report_json"], **overview}


def run(argv: list[str] | None = None) -> Any:
    """The result of one command (raises the tool's input errors)."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("describe").add_argument("principle")
    commands.add_parser("describe_marker").add_argument("name")
    commands.add_parser("prepare").add_argument("task_dir")
    evaluate_cmd = commands.add_parser("evaluate")
    evaluate_cmd.add_argument("task_dir")
    evaluate_cmd.add_argument("targets_dir")
    evaluate_cmd.add_argument("--out", default=str(REPORTS))
    explain = commands.add_parser("explain")
    explain.add_argument("report")
    explain.add_argument("target")
    explain.add_argument("principle")
    args = parser.parse_args(argv)

    from pythonarchtesting.mcp_server import markers, principles, reports, tasks

    if args.command == "describe":
        return principles.describe_principle(args.principle)
    if args.command == "describe_marker":
        return markers.describe_marker(args.name)
    if args.command == "prepare":
        return tasks.prepare_task(_abs(args.task_dir))
    if args.command == "evaluate":
        return evaluate(args.task_dir, args.targets_dir, args.out)
    return reports.explain_target(
        _abs(args.report), args.target, principle=args.principle
    )


def main(argv: list[str] | None = None) -> int:
    from pythonarchtesting.exceptions import ConfigurationError
    from pythonarchtesting.mcp_server.errors import ToolInputError

    try:
        result = run(argv)
    except (ToolInputError, ValueError, ConfigurationError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
