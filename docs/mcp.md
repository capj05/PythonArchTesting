# MCP server

An optional [Model Context Protocol](https://modelcontextprotocol.io) server
lets an AI client author markers, run evaluations, and read the saved JSON
reports. It adds no logic of its own: every tool calls the same code as the
CLI. The server never edits reference or student files; the only thing it
writes is the run directory of `run_evaluation`.

## Installation

```bash
pip install "pythonarchtesting[mcp]"
```

The `mcp` extra is not part of the base install; `import pythonarchtesting`
never imports it. The console script `python-arch-test-mcp` starts the server
on stdio.

The marker catalogue is read from `docs/markers` in a checkout. An install
ships those pages as data files under `share/pythonarchtesting/markers` (also
checked under the user base for `pip install --user`). When neither copy is
found, the tools fail with `marker documentation not found; reinstall
pythonarchtesting[mcp]`.

For Claude Code, add it to `.mcp.json`:

```json
{"mcpServers": {"pythonarchtesting": {"command": "python-arch-test-mcp"}}}
```

## Tools

| Tool | Read-only | Purpose |
|------|-----------|---------|
| `list_markers(category=None)` | yes | Catalogue; each entry has `name`, `category`, `placement`, `requires_dynamic` and `summary`. `category` matches case-insensitively; an unknown one is a tool error listing the known categories. |
| `describe_marker(name)` | yes | One marker: `name`, `category`, `placement`, `requires_dynamic` and `markdown`, the full documentation page. |
| `validate_declarations(source, reference_modules=None, validation_scope="all", config=None)` | yes | The CLI's `--validate-declarations`: diagnostics for every marker in the reference. Runs no target code. |
| `run_evaluation(source, output_dir, targets=None, targets_dir=None, project_pattern=None, exclude_patterns=None, reference_modules=None, validation_scope="all", dynamic=False, sandbox=None, sandbox_memory_mb=1024, config=None)` | no | Runs what the CLI runs and writes `report.json` and the Markdown report into a new timestamped subdirectory of `output_dir`. Reports progress per target. |
| `summarize_report(report_path, offset=0, limit=50)` | yes | Totals, rules ranked by number of failing targets, a page of targets. |
| `explain_target(report_path, target, include_passed=False, offset=0, limit=20)` | yes | The failing and warning results of one submission, with evidence. |
| `explain_rule(report_path, rule, offset=0, limit=50)` | yes | One rule across all targets. |

## Workflow

1. Find markers with `list_markers` and `describe_marker`.
2. Edit the reference files with the client's own file tools.
3. After every marker change, run `validate_declarations`.
4. Verify a marker with `run_evaluation` on the reference as the only target
   (it must pass) and on a copy you deliberately broke (it must fail). Each
   run gets its own directory, so both reports survive.
5. Evaluate a batch with `targets_dir`.
6. Read the result with `summarize_report`, then `explain_target` or
   `explain_rule`. A rule that fails almost every submission points to a wrong
   marker rather than wrong students.

## Paths, config and sandbox

- Every path argument must be absolute; a relative path is a tool error,
  because the server's working directory is whatever the client chose.
- Give exactly one of `targets` and `targets_dir`; `project_pattern` and
  `exclude_patterns` need `targets_dir`. `validation_scope` is `all` or
  `logical-views`.
- `config` names a configuration file. Without it the server looks for
  `.pythonarchtesting` in the directory of `source`, then in its parent
  directory. The working directory and
  `PYTHON_ARCH_TARGET_PATH` are never consulted. Each result states which
  config applied, or `defaults`.
- `dynamic=True` runs student code. `sandbox` then defaults to `bwrap`; an
  unavailable `bwrap` is an error, never a silent fallback. `limits` can be
  requested explicitly; `none` is rejected. `sandbox_memory_mb` (default
  `1024`) must be positive. `sandbox` and `sandbox_memory_mb` are an error
  without `dynamic`. See [dynamic-checks.md](dynamic-checks.md).
- Without `dynamic`, runtime rules are reported as `SKIPPED`. Every
  `run_evaluation` result carries `runtime_rules_skipped`, the number of
  results skipped because `dynamic` was off (`0` when it was on).
- A run blocks until it ends. Reports are described in
  [reporting.md](reporting.md).
