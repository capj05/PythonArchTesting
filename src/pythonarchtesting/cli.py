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
    build_report,
    generate_multi_target_report,
    generate_validation_report,
    get_multi_exit_code,
)
from pythonarchtesting.validation_scope import VALIDATION_SCOPE_ALL, VALIDATION_SCOPES


def run_multi(*args: Any, **kwargs: Any) -> Any:
    from pythonarchtesting.runner_multi import run_multi as _run_multi

    return _run_multi(*args, **kwargs)


def ProjectState(*args: Any, **kwargs: Any) -> Any:
    from pythonarchtesting.state import ProjectState as _project_state

    return _project_state(*args, **kwargs)


def _parse_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Python Architecture Testing CLI")
    parser.add_argument("--config", help="Path to custom configuration file")
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


def _run_single_target(
    config: Config,
    target_path: str,
    reference_modules: Optional[List[str]],
    output_file: Optional[str],
    output_format: Optional[str],
    validation_scope: str = VALIDATION_SCOPE_ALL,
) -> int:
    state = ProjectState(
        target_path=target_path,
        reference_modules=reference_modules or [],
        config=config,
        validation_scope=validation_scope,
    )
    state.analyze()

    report = generate_validation_report(state, output_format or "json", config=config)
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report written to {output_file}")
    else:
        print(report)

    report_data = build_report(state, config)
    exit_code = int(report_data.get("exit_code", 0))
    if exit_code != 0:
        print(f"Validation failed for {target_path}")
    return exit_code


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
    from pythonarchtesting.runner_multi.source_prep import prepare_source

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

    if (
        args.target
        and len(args.target) > 1
        and not (args.source or args.targets or args.targets_dir)
    ):
        parser.error(
            "Multiple --target values require multi-target flags. "
            "Use --targets/--targets-dir (and optionally --source), "
            "or pass a single --target."
        )

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

    multi_requested = bool(
        args.source
        or args.targets_dir
        or args.targets
        or (args.target and len(args.target) > 1)
    )

    config_targets = config.projects.targets
    config_targets_dir = config.projects.targets_dir
    config_indicates_multi = bool(config_targets_dir) or len(config_targets) > 1

    explicit_single = bool(args.target and len(args.target) == 1) and not (
        args.targets or args.targets_dir or args.source
    )

    if explicit_single:
        use_multi = False
    else:
        use_multi = (
            multi_requested or config_indicates_multi or len(projects_cfg.targets) > 1
        )

    if use_multi:
        if args.format == "markdown" and not args.output:
            parser.error(
                "Multi-target markdown reporting requires --output <directory>."
            )
        run_state, target_states = run_multi(
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
        report = generate_multi_target_report(
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
        return get_multi_exit_code(run_state, target_states, config)

    target_path = projects_cfg.targets[0].path
    return _run_single_target(
        config=config,
        target_path=str(target_path),
        reference_modules=reference_modules,
        output_file=args.output,
        output_format=args.format,
        validation_scope=args.validation_scope,
    )


if __name__ == "__main__":
    sys.exit(main())
