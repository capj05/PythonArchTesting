"""
Command-line interface for Python Architecture Testing.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, List, Optional

from pythonarchtesting.config import Config, load_config, resolve_projects_config
from pythonarchtesting.infrastructure.logging import configure_logging
from pythonarchtesting.report.lazy import (
    generate_run_report,
    get_run_exit_code,
)
from pythonarchtesting.validation_scope import VALIDATION_SCOPE_ALL, VALIDATION_SCOPES


def run_projects(*args: Any, **kwargs: Any) -> Any:
    from pythonarchtesting.runner import run_projects as _run_projects

    return _run_projects(*args, **kwargs)


def _parse_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Python Architecture Testing CLI")
    parser.add_argument(
        "--config",
        help=(
            "Explicit configuration file path; when omitted, the CLI auto-loads "
            "'.pythonarchtesting' from the current working directory"
        ),
    )
    parser.add_argument("--source", help="Source path for reference modules")
    parser.add_argument(
        "--target",
        action="append",
        help="Target project path (repeatable)",
    )
    parser.add_argument(
        "--targets",
        help="Comma-separated list of target project paths",
    )
    parser.add_argument(
        "--targets-dir",
        help="Directory containing target subprojects",
    )
    parser.add_argument(
        "--reference-modules",
        help="Comma-separated list of reference modules",
    )
    parser.add_argument(
        "--project-pattern",
        help="Glob pattern for targets-dir subdirectories",
    )
    parser.add_argument(
        "--exclude-patterns",
        help="Comma-separated exclude patterns for targets-dir",
    )
    parser.add_argument(
        "--format",
        default="json",
        choices=["json", "markdown"],
        help="Report output format",
    )
    parser.add_argument(
        "--output",
        help="Output file path (prints to stdout if omitted)",
    )
    parser.add_argument(
        "--validate-declarations",
        action="store_true",
        help="Validate reference annotation declarations without analyzing targets",
    )
    parser.add_argument(
        "--validation-scope",
        default=VALIDATION_SCOPE_ALL,
        choices=list(VALIDATION_SCOPES),
        help="Limit validation to a specific scope",
    )
    return parser


def _run_declaration_validation(
    config: Config,
    source_path: str,
    reference_modules: Optional[List[str]],
    output_file: Optional[str],
    output_format: Optional[str],
    validation_scope: str = VALIDATION_SCOPE_ALL,
) -> int:
    from pythonarchtesting.declaration_validation import (
        build_declaration_validation_report,
        get_declaration_validation_exit_code,
    )
    from pythonarchtesting.runner.source_prep import prepare_source

    run_state = prepare_source(
        config=config,
        source_path=Path(source_path),
        reference_modules=reference_modules or None,
        validation_scope=validation_scope,
    )
    report = build_declaration_validation_report(run_state, output_format or "json")
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report written to {output_file}")
    else:
        print(report)
    return get_declaration_validation_exit_code(run_state)


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config_warnings: List[Any] = []
    config = load_config(
        config_path=args.config,
        cli_args={"output_format": getattr(args, "format", None)},
        discover_from_cwd=args.config is None,
        cwd=os.getcwd(),
        warning_sink=config_warnings.append,
    )

    configure_logging(config)
    for warning in config_warnings:
        logging.warning("%s: %s", warning.code, warning.message)

    explicit_targets: List[str] = []
    if args.target:
        explicit_targets.extend(args.target)
    explicit_targets.extend(_parse_csv(args.targets))

    reference_modules = _parse_csv(args.reference_modules)
    project_pattern = args.project_pattern
    exclude_patterns = _parse_csv(args.exclude_patterns) or None

    if args.validate_declarations:
        if args.format != "json":
            parser.error("Declaration validation supports only --format json.")
        if (
            args.target
            or args.targets
            or args.targets_dir
            or args.project_pattern
            or args.exclude_patterns
        ):
            parser.error(
                "--validate-declarations is source-only and does not accept target "
                "selection flags."
            )

        config_source_path = getattr(
            getattr(config, "projects", None), "source_path", None
        )
        has_config_source = config_source_path not in (None, "", Path("."))
        if not args.source and not reference_modules and not has_config_source:
            parser.error(
                "--validate-declarations requires --source, --reference-modules, "
                "or a configured [projects].source_path."
            )

        resolved_source_path = str(args.source or config_source_path or Path("."))
        return _run_declaration_validation(
            config=config,
            source_path=resolved_source_path,
            reference_modules=reference_modules,
            output_file=args.output,
            output_format=args.format,
            validation_scope=args.validation_scope,
        )

    projects_cfg = resolve_projects_config(
        config=config,
        source_path=args.source,
        targets=explicit_targets or None,
        targets_dir=args.targets_dir,
        project_pattern=project_pattern,
        exclude_patterns=exclude_patterns,
        env_target_path=os.environ.get("PYTHON_ARCH_TARGET_PATH"),
    )

    if args.format == "markdown" and not args.output:
        parser.error("Markdown reporting requires --output <directory>.")
    run_state, target_states = run_projects(
        config=config,
        projects=projects_cfg,
        source_path=args.source,
        targets=explicit_targets or None,
        targets_dir=args.targets_dir,
        reference_modules=reference_modules or None,
        project_pattern=project_pattern,
        exclude_patterns=exclude_patterns,
        validation_scope=args.validation_scope,
        load_config_first=False,
    )
    report = generate_run_report(
        run_state, target_states, args.format, config, args.output
    )
    if args.output and args.format == "json":
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report written to {args.output}")
    elif args.output and args.format == "markdown":
        print(f"Report written to {report}")
    else:
        print(report)
    return get_run_exit_code(run_state, target_states, config)


if __name__ == "__main__":
    sys.exit(main())
