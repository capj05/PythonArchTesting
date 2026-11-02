"""Command-line access to the authoring tools for the E4 agents.

The agents of the marker-authoring experiment (E4) cannot reach the MCP
server, so this script gives them the same tools from a shell, printing JSON:

- ``validate REFERENCE`` — the MCP ``validate_declarations``;
- ``evaluate REFERENCE TARGET`` — evaluate ``TARGET`` against ``REFERENCE``
  with ``--dynamic`` (sandbox ``limits``) and list the results that did not
  pass; on the unchanged solution every marker should pass;
- ``check-cases REFERENCE ENTRY CASES_JSON`` — the MCP ``check_cases``;
- ``verify-marker REFERENCE RULE [--operators a,b] [--files x.py,y.py]
  [--dynamic]`` — the MCP ``verify_marker``.

The last two are available only in condition B of the experiment.

Usage::

    python example/llm_authoring/tools.py validate /abs/path/reference
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _evaluate(reference: str, target: str) -> dict[str, Any]:
    from pythonarchtesting.config import load_config
    from pythonarchtesting.dynamic.sandbox import SandboxPolicy
    from pythonarchtesting.runner import run_projects

    _, states = run_projects(
        config=load_config(cli_args={"output_format": "json"}, discover_from_cwd=False),
        source_path=reference,
        targets=[target],
        load_config_first=False,
        dynamic=True,
        sandbox=SandboxPolicy(mode="limits", memory_mb=1024),
    )
    (state,) = states
    problems = [
        {
            "rule": result.rule_id,
            "status": result.status,
            "summary": (result.details or {}).get("summary") or result.message,
        }
        for result in state.rule_results
        if result.status != "OK"
    ]
    return {
        "results": len(state.rule_results),
        "not_ok": len(problems),
        "problems": problems[:40],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("reference")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("reference")
    evaluate.add_argument("target")
    cases = commands.add_parser("check-cases")
    cases.add_argument("reference")
    cases.add_argument("entry")
    cases.add_argument("cases_json", help="a JSON list of cases, or @file")
    verify = commands.add_parser("verify-marker")
    verify.add_argument("reference")
    verify.add_argument("rule")
    verify.add_argument("--operators")
    verify.add_argument("--files")
    verify.add_argument("--dynamic", action="store_true")
    verify.add_argument("--detail", choices=["problems", "all"], default="problems")
    args = parser.parse_args()

    from pythonarchtesting.exceptions import ConfigurationError
    from pythonarchtesting.mcp_server import authoring, evaluation
    from pythonarchtesting.mcp_server.errors import ToolInputError

    try:
        if args.command == "validate":
            result: Any = evaluation.validate_declarations_tool(
                str(Path(args.reference).resolve())
            )
        elif args.command == "evaluate":
            result = _evaluate(
                str(Path(args.reference).resolve()), str(Path(args.target).resolve())
            )
        elif args.command == "check-cases":
            raw = args.cases_json
            text = (
                Path(raw[1:]).read_text(encoding="utf-8")
                if raw.startswith("@")
                else raw
            )
            result = authoring.check_cases(
                str(Path(args.reference).resolve()),
                args.entry,
                json.loads(text),
                sandbox="limits",
            )
        else:
            result = authoring.verify_marker(
                str(Path(args.reference).resolve()),
                args.rule,
                operators=args.operators.split(",") if args.operators else None,
                files=args.files.split(",") if args.files else None,
                dynamic=args.dynamic,
                sandbox="limits" if args.dynamic else None,
                detail=args.detail,
            )
            # ``why`` says why a mutant did not run or what killed it; the
            # first measurement (runs 1-2) and the second (runs 3-6) of E4
            # were made without it.
            result["mutants"] = [
                {
                    k: m[k]
                    for k in ("operator", "file", "description", "outcome", "why")
                    if k in m
                }
                for m in result["mutants"]
            ]
    except (ToolInputError, ValueError, ConfigurationError, OSError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(result, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
