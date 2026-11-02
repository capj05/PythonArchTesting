"""
Command-line interface for Python Architecture Testing.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from pythonarchtesting.config import Config, load_config, resolve_projects_config
from pythonarchtesting.exceptions import ConfigurationError, MappingError
from pythonarchtesting.infrastructure.logging import configure_logging
from pythonarchtesting.report.lazy import (
    generate_run_report,
    get_run_exit_code,
)
from pythonarchtesting.validation_scope import VALIDATION_SCOPE_ALL, VALIDATION_SCOPES


def run_projects(*args: Any, **kwargs: Any) -> Any:
    from pythonarchtesting.runner import run_projects as _run_projects

    return _run_projects(*args, **kwargs)


USAGE_ERROR_EXIT_CODE = 2


def _write_report(output_path: str, report: str) -> None:
    """Write a report, creating the output directory when it is missing.

    Mirrors the Markdown bundle, which already creates its own directory.
    """
    path = Path(output_path)
    if path.parent != Path(""):
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")


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
    parser.add_argument(
        "--dynamic",
        action="store_true",
        help=(
            "Run the runtime rules (calls between modules, imports, attribute "
            "writes, instantiation, class shape, design patterns, flow order) "
            "by executing target code in a child interpreter; without it those "
            "rules are SKIPPED"
        ),
    )
    parser.add_argument(
        "--architecture",
        action="store_true",
        help=(
            "Compare the target with the module dependencies of the reference "
            "even where the reference declares no architecture_entry; only "
            "the static comparison, as no entry function is known"
        ),
    )
    parser.add_argument(
        "--write-model",
        metavar="FILE",
        help=(
            "Write the reference's architecture model (modules, imports, "
            "libraries, the architecture_entry declaration; with --dynamic also "
            "what the declared cases do) as JSON to FILE and stop; needs only "
            "--source"
        ),
    )
    parser.add_argument(
        "--mapping",
        help=(
            "JSON file pairing reference entities with target entities the "
            'matching could not pair: {"pairs": {"controller": "handler"}}, '
            'or per target {"targets": {"<id>": {"pairs": ...}}}; every '
            "pair is checked, and automatic matches are never overridden"
        ),
    )
    parser.add_argument(
        "--sandbox",
        default="limits",
        choices=["none", "limits", "bwrap"],
        help=(
            "How --dynamic confines target code: 'limits' (default) caps memory, "
            "CPU time, processes and file sizes and scrubs the environment, but "
            "leaves the file system and network open; 'bwrap' adds no network "
            "and a read-only file system without your home directory; 'none' "
            "only isolates the process"
        ),
    )
    parser.add_argument(
        "--sandbox-memory-mb",
        type=int,
        default=1024,
        help=(
            "Data-segment (heap) limit per child interpreter with --sandbox "
            "limits/bwrap"
        ),
    )
    return parser


def _load_mapping(
    parser: Any, path: Optional[str]
) -> Optional[Dict[str, Dict[str, str]]]:
    """The assisted pairing in ``--mapping``, or ``None`` without one."""
    if not path:
        return None
    from pythonarchtesting.matching.assisted import load_mapping

    try:
        return load_mapping(Path(path))
    except (OSError, ValueError) as exc:
        parser.error(f"--mapping {path}: {exc}")
    return None


def _sandbox_policy(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> Optional[Any]:
    """Build and check the sandbox for a --dynamic run; None for static runs."""
    if not args.dynamic:
        if args.sandbox != parser.get_default(
            "sandbox"
        ) or args.sandbox_memory_mb != parser.get_default("sandbox_memory_mb"):
            parser.error("--sandbox and --sandbox-memory-mb apply only with --dynamic.")
        return None
    from pythonarchtesting.dynamic.sandbox import (
        SandboxPolicy,
        SandboxUnavailableError,
        check_available,
    )

    if args.sandbox_memory_mb <= 0:
        parser.error("--sandbox-memory-mb must be positive.")
    policy = SandboxPolicy(mode=args.sandbox, memory_mb=args.sandbox_memory_mb)
    try:
        check_available(policy)
    except SandboxUnavailableError as exc:
        parser.error(f"--sandbox {args.sandbox} is not available here: {exc}")
    return policy


def _run_declaration_validation(
    config: Config,
    source_path: str,
    reference_modules: Optional[List[str]],
    output_file: Optional[str],
    output_format: Optional[str],
    validation_scope: str = VALIDATION_SCOPE_ALL,
) -> int:
    from pythonarchtesting.declaration_validation import validate_declarations

    if (output_format or "json") != "json":
        raise ValueError(
            f"Unsupported declaration validation output format: {output_format}"
        )
    payload = validate_declarations(
        config, Path(source_path), reference_modules or None, validation_scope
    )
    exit_code = payload.pop("exit_code")
    report = json.dumps(payload, indent=2, sort_keys=True)
    if output_file:
        _write_report(output_file, report)
        print(f"Report written to {output_file}")
    else:
        print(report)
    return int(exit_code)


def _write_model(
    config: Config, args: argparse.Namespace, source_path: str, sandbox: Any
) -> int:
    from pythonarchtesting.architecture.model import describe
    from pythonarchtesting.runner.source_prep import prepare_source

    source = Path(source_path).expanduser().resolve()
    state = prepare_source(
        config=config,
        source_path=source,
        reference_modules=_parse_csv(args.reference_modules) or None,
    )
    model = describe(
        state,
        mode="full" if args.dynamic else "static",
        source_root=source,
        sandbox=sandbox,
    )
    _write_report(args.write_model, json.dumps(model, indent=2, sort_keys=True))
    print(f"Model written to {args.write_model}")
    for problem in model["declaration"].get("problems") or []:
        print(
            f"warning: the architecture_entry declaration does not compile: {problem}",
            file=sys.stderr,
        )
    runtime = model.get("runtime") or {}
    if runtime.get("status") not in (None, "completed"):
        why = runtime.get("reason") or runtime.get("error") or runtime.get("status")
        print(f"warning: the reference's cases did not run: {why}", file=sys.stderr)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Run the CLI, turning expected failures into a one-line message.

    Argument errors keep going through ``parser.error``, which raises
    ``SystemExit(2)``; this wrapper gives configuration and I/O failures the same
    exit code instead of letting a traceback reach the user.
    """
    try:
        return _run(argv)
    except ConfigurationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return USAGE_ERROR_EXIT_CODE
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return USAGE_ERROR_EXIT_CODE


def _run(argv: Optional[List[str]] = None) -> int:
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

    if args.write_model:
        ignored = [
            flag
            for flag, given in (
                (
                    "--target/--targets/--targets-dir",
                    args.target or args.targets or args.targets_dir,
                ),
                ("--project-pattern", args.project_pattern),
                ("--exclude-patterns", args.exclude_patterns),
                ("--validate-declarations", args.validate_declarations),
                ("--architecture", args.architecture),
                ("--mapping", args.mapping),
                ("--output", args.output),
                ("--format", args.format != "json"),
            )
            if given
        ]
        if ignored:
            parser.error(
                "--write-model describes the reference only and writes FILE; "
                f"drop {', '.join(ignored)}."
            )
        source = args.source or getattr(
            getattr(config, "projects", None), "source_path", None
        )
        if source in (None, "", Path(".")):
            parser.error(
                "--write-model requires --source or a configured [projects].source_path."
            )
        return _write_model(config, args, str(source), _sandbox_policy(parser, args))

    if args.validate_declarations:
        if args.dynamic:
            parser.error("--validate-declarations runs no target code; drop --dynamic.")
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
    try:
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
            dynamic=args.dynamic,
            sandbox=_sandbox_policy(parser, args),
            architecture=args.architecture,
            mappings=_load_mapping(parser, args.mapping),
        )
    except MappingError as exc:
        parser.error(str(exc))
    from pythonarchtesting.runner.skips import (
        count_results_undecided,
        count_runtime_results_unverified,
        count_runtime_rules_skipped,
    )

    skipped = count_runtime_rules_skipped(target_states)
    if skipped:
        # Otherwise a run without --dynamic reads as a pass for every target.
        print(
            f"warning: {skipped} runtime rule result(s) were SKIPPED because "
            "--dynamic was not given; their targets are not checked by them",
            file=sys.stderr,
        )
    unverified = count_runtime_results_unverified(target_states)
    if unverified:
        # A runtime pass holds only for the code its cases ran.
        print(
            f"warning: {unverified} runtime rule result(s) passed with code or "
            "cases left unchecked; see details.unverified",
            file=sys.stderr,
        )
    undecided = count_results_undecided(target_states)
    if undecided:
        # The policy could not judge these changes; a person has to.
        print(
            f"warning: {undecided} result(s) passed with undecided architecture "
            "changes; see details.undecided",
            file=sys.stderr,
        )
    report = generate_run_report(
        run_state, target_states, args.format, config, args.output
    )
    if args.output and args.format == "json":
        # generate_run_report already wrote the file when given an output path.
        print(f"Report written to {args.output}")
    elif args.output and args.format == "markdown":
        print(f"Report written to {report}")
    else:
        print(report)
    return get_run_exit_code(run_state, target_states, config)


if __name__ == "__main__":
    sys.exit(main())
