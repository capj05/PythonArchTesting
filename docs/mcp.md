# MCP server

An optional [Model Context Protocol](https://modelcontextprotocol.io) server
lets an AI client author markers, run evaluations, and read the saved JSON
reports. It adds no logic of its own: every tool calls the same code as the
CLI. The server never edits reference or student files and never calls an
LLM; the only thing it keeps is the run directory of `run_evaluation`
(`verify_marker` works on temporary copies it deletes afterwards).

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
| `check_cases(source, entry, cases, init=None, min_coverage=0.8, timeout_s=5.0, sandbox=None, sandbox_memory_mb=1024, config=None)` | no | Runs proposed `cases` of the reference function `entry` (`"module.function"`) on the reference, sandboxed. `accepted` when every case runs (an exception the reference raises on purpose is reported, not rejected) and the cases ran at least `min_coverage` of the entry's lines; `reasons`, `coverage.unexercised_lines` and the calls between modules the cases drove (`edges`) say what to change. Use before putting cases into a runtime marker or `architecture_entry`. |
| `verify_marker(source, rule, operators=None, files=None, libraries=None, max_mutants=100, dynamic=False, sandbox=None, sandbox_memory_mb=1024, config=None, detail="problems")` | no | Seeds architectural violations into copies of the reference with named operators: `add_import` (a module imports a project module it did not), `lazy_import` (the same inside its first function), `add_library` (`import pickle`, or `libraries`), `rebuild_injected` (a constructor builds its own collaborator of the injected one's class), `drop_call` (a method no longer calls `self.<collaborator>.<method>(...)`). `rule` (a marker name or a rule id prefix) must fail on each mutant (`killed`) and pass on the unchanged reference (`reference_passes`). Without `operators` only the operators the marker can see are used (import markers: the import operators; `forbid_runtime_instantiation`: `rebuild_injected`; delegation and call markers: `drop_call`; a marker no operator can break needs `operators`); without `files` only the files of the entities the marker is declared on (every file for a marker on the root package). `scope` says which were used. Only the rules `rule` names are evaluated. `by_operator` counts killed, survived and not-run mutants per operator; `mutants` lists the survivors and the mutants that did not run (`detail="all"`: every mutant). `accepted` when the reference passes, every mutant is killed and the sample was not cut (`truncated`). A survivor is a violation the marker misses or a change the architecture allows. A marker checked only at run time needs `dynamic=True`. The target must be one project: a directory holding several is evaluated as one and is not rejected. |
| `describe_architecture(source, mode="static", sandbox=None, sandbox_memory_mb=1024, config=None)` | no | The reference's architecture model, what `architecture_entry` compares a target with: `modules` (name, file), `static.imports` and `static.external` (each `edge` with the line that makes it, `at`), the `declaration` (`declared`, `policy`, `allow`, `forbid`, `ignore_external`, `ignore_type_checking`, and with a runtime part `entry`, `case_count`, `require_all`; without a declaration the defaults `--architecture` uses; a declaration that does not compile has only `declared` and `problems`, since no rule exists), and `compared`, when a target is compared with it at all (`static`: `always`, `with --architecture` or `never`, e.g. for a broken declaration or a reference that is no package; `runtime`: `with --dynamic` or `never`). `mode="full"` also runs the declared cases on the reference, sandboxed, and adds `runtime`: `calls`, `instances` (`"module -> module.Class"`), `external` (libraries the cases called), `libraries_compared` (what a target may call: those plus every library the reference imports), `coverage` and the cases' status. `status` is `completed` only when every case ran; otherwise (`reference_failed`, with `error`) the comparison would end in `ERROR` and judge nothing. Without `entry` and `cases`, or with a broken declaration, `reason` says why nothing ran. Edges are written as exceptions take them (`"a -> b"`, the package itself `__init__`). Libraries the declaration ignores and the markers' own package (`pythonarchtesting`, which the comparison counts as a reference library) are left out. `source` is resolved like the evaluation resolves it, since its last part is the package name. Describes, never judges; the CLI writes the same JSON with `--write-model`. |
| `run_evaluation(source, output_dir, targets=None, targets_dir=None, project_pattern=None, exclude_patterns=None, reference_modules=None, validation_scope="all", dynamic=False, sandbox=None, sandbox_memory_mb=1024, config=None, architecture=False, mapping=None)` | no | Runs what the CLI runs (`architecture` is `--architecture`, `mapping` the content of a `--mapping` file) and writes `report.json` and the Markdown report into a new timestamped subdirectory of `output_dir`. Reports progress per target. |
| `summarize_report(report_path, offset=0, limit=50)` | yes | Totals, rules ranked by number of failing targets, a page of targets. |
| `check_architecture(source, target, mode="static", mapping=None, sandbox=None, sandbox_memory_mb=1024, config=None)` | no | One target against the reference, for an agent that fixes code in a loop: the same evaluation as the CLI with `--architecture` (and `--dynamic` in `mode="full"`), returned directly instead of written. `passed`, `complete` (false when a part was `SKIPPED`, e.g. runtime checks in static mode: the pass then holds only for what ran), `reference_problems` (markers of the reference that do not compile: fix the reference, not the target), `problems` (each with `feedback`, below), `undecided` changes, counts of `skipped` and `unpaired` results, and with a `mapping` the pairs `applied` and `refused` (with the reason). |
| `propose_mapping(report_path, target)` | yes | The reference entities one target left unpaired (the source of `required_target_missing`), each with its kind, matching status and best candidates in the target, plus an empty `mapping_template`, and `paired_by_name`, the pairs the matching made by name only (rule `unique_name` or `member_of_paired_class`; worth a look, a mapping replaces them). Propose pairs from it and pass them as `run_evaluation(mapping=...)`; see [reporting.md](reporting.md#assisted-pairing). |
| `explain_target(report_path, target, include_passed=False, offset=0, limit=20)` | yes | The failing and warning results of one submission, with evidence and `feedback`. |
| `explain_rule(report_path, rule, offset=0, limit=50)` | yes | One rule across all targets. |

## Workflow

1. Find markers with `list_markers` and `describe_marker`.
2. Edit the reference files with the client's own file tools.
3. After every marker change, run `validate_declarations`.
4. Check the cases of a runtime marker with `check_cases`, and verify the
   marker with `verify_marker`: it must pass on the reference and fail on
   every seeded violation it is meant to catch. A hand-made broken copy can
   still be checked with `run_evaluation` on it.
5. Before writing exceptions or feedback about the architecture, read the
   reference's model with `describe_architecture` (`mode="full"` for what
   the cases do at run time).
6. Evaluate a batch with `targets_dir`.
7. Read the result with `summarize_report`, then `explain_target` or
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
- `check_cases` always runs the reference, so it always uses the sandbox
  rules below as if `dynamic` were on.
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

## Feedback

Every problem result that `explain_target`, `explain_rule` and
`check_architecture` return carries `feedback`: the material for explaining the
result to a student, never the explanation itself (the server does not call an
LLM).

- `rule`, `marker`, `status`, `summary` and `hints` (the fix hints);
- `issues`, at most five (`issues_total` counts all): for `architecture_entry`
  each divergent edge with its `layer`, and `file`, `module` and `line` of the
  target's code that makes it. The `edge` is named by the reference's modules
  (a renamed or folded module stands for the reference's), `module`/`file`
  are the target's own. `reference_allows` lists the reference's edges from
  the same module (not for the `external` layer: a library the reference uses
  is allowed from any module). With `require_all`, an `absent` edge has no
  place in the target; `reference_module` and `reference_line` say where the
  reference makes the call; for `enforce_layers` each path with
  its `kind` (`upward`, `sibling`, `skip`), `path` of modules and the first
  import's `file` and `line`; for `forbid_cycles` each cycle; for other rules
  their violations, or the summary;
- `undecided`, when the result lists changes nothing decided.

