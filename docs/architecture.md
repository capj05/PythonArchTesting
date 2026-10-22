# Architecture

This is the current high-level pipeline for PythonArchTesting.

## Pipeline

1. CLI orchestration starts in `pythonarchtesting.cli`.
2. Source entities and declaration metadata are extracted from the reference
   project in `pythonarchtesting.entities_extraction`.
3. Declaration entries are normalized and compiled into rules in
   `pythonarchtesting.rules.compilation`.
4. Source entities are matched to target entities in `pythonarchtesting.matching`.
5. Compiled rules are evaluated in `pythonarchtesting.execution.evaluators`.
6. Reports are built and rendered in `pythonarchtesting.report`.

For run execution, the `pythonarchtesting.runner` package prepares shared
source state once (`runner.source_prep`) and evaluates each target separately
(`runner.target_eval`); `runner.orchestrator` coordinates both single-target
and multi-target runs. `run_projects` accepts `on_target_done(done, total,
target_id)` to report progress per target. `runner.skips` counts the runtime
results skipped because `--dynamic` was missing (the CLI warning, and
`runtime_rules_skipped` in the MCP server). The declaration validation shared by
`--validate-declarations` and the MCP server lives in
`pythonarchtesting.declaration_validation`.

## Key Modules

### Declaration Surface

- `pythonarchtesting.rules`
- `pythonarchtesting.rules.declaration.core`

`pythonarchtesting.rules` is the public import surface for marker factories. Add or change
user-facing declaration helpers here.

### Extraction And Normalization

- `pythonarchtesting.entities_extraction.annotations`
- `pythonarchtesting.rules.compilation.declarations`

This layer parses annotation metadata, validates supported shapes, and
normalizes them into shared declaration entries.

### Rule Compilation

- `pythonarchtesting.rules.compilation.orchestrator`
- `pythonarchtesting.rules.compilation.decorators.api_signature`
- `pythonarchtesting.rules.compilation.decorators.attributes`
- `pythonarchtesting.rules.compilation.decorators.constructors`
- `pythonarchtesting.rules.compilation.decorators.enum_type`
- `pythonarchtesting.rules.compilation.decorators.factories`
- `pythonarchtesting.rules.compilation.decorators.flow`
- `pythonarchtesting.rules.compilation.decorators.import_policy`
- `pythonarchtesting.rules.compilation.decorators.member_absence`
- `pythonarchtesting.rules.compilation.decorators.member_set`
- `pythonarchtesting.rules.compilation.decorators.method_set`
- `pythonarchtesting.rules.compilation.decorators.nominal_type`
- `pythonarchtesting.rules.compilation.decorators.protocols`
- `pythonarchtesting.rules.compilation.decorators.python_modifiers`
- `pythonarchtesting.rules.compilation.decorators.runtime_structure`

`pythonarchtesting.rules.compilation` is the canonical compiler namespace.
Each decorator module turns its normalized declaration entries into rule
objects, compiler evidence, and compiler-side results. Marker factories on the
public `pythonarchtesting.rules` surface dispatch into these modules through
the orchestrator.

### Matching

- `pythonarchtesting.matching.engine`
- `pythonarchtesting.matching.candidates`
- `pythonarchtesting.matching.models`

Matching chooses the best target entity for each source entity and records
confidence and candidate details for reporting.

### Evaluation

- `pythonarchtesting.execution.evaluators.api_signature`
- `pythonarchtesting.execution.evaluators.import_policy`
- `pythonarchtesting.execution.evaluators.protocol_conformance`
- `pythonarchtesting.execution.evaluators.variable_flow`
- `pythonarchtesting.execution.evaluators.registry`

Each evaluator owns one rule family and produces result rows with messages, fix
hints, evidence, and status.

### Dynamic Checks

- `pythonarchtesting.execution.evaluators.runtime_structure`
- `pythonarchtesting.execution.evaluators.runtime_imports`
- `pythonarchtesting.execution.evaluators.runtime_flow`
- `pythonarchtesting.dynamic.batch`
- `pythonarchtesting.dynamic.sandbox`
- `pythonarchtesting.dynamic.runner`
- `pythonarchtesting.dynamic.probe`

`runtime_calls`, `runtime_reference_calls`, `runtime_writes`,
`runtime_instances`, `runtime_members`, `runtime_class_kind`,
`runtime_protocol`, `runtime_pattern`, `runtime_imports`, and `runtime_flow`
are the only evaluators that execute target code, and only
when the run was started with `--dynamic`: `run_projects(dynamic=True)` sets
`RunState.dynamic_enabled`, and `runner.target_eval` then passes the target root
to evaluation as `EvalContext.target_root`. When it is `None`, the evaluator
returns `SKIPPED` without starting anything.

Before a target's rules are evaluated, `dynamic.batch.prefetch` groups the
matched call, write, instance, and class rules by target module and runs each group of two or
more as one batch (`runner.run_case_batch`); the probe bounds each job with an
interval timer. Outcomes land in `EvalContext.dynamic_cache`, which the
evaluator reads first. A batch that times out or crashes as a whole is not
cached, so its rules fall back to one interpreter each. `runtime_flow`
(`enforce_flow` with `cases`) and `runtime_reference_calls` run the reference
from `EvalContext.source_root` first, to record each stage's calls or the
module call graph, then the target.

Every child interpreter is confined by the run's `dynamic.sandbox.SandboxPolicy`
(`--sandbox`): `limits` sets POSIX resource limits in a pre-exec hook and
replaces the environment; `bwrap` also wraps the command in bubblewrap with
read-only binds of only the paths the interpreter, the framework, and the
analysed project need. The CLI checks that `bwrap` can start an interpreter
before any target is analysed. The policy travels as `RunState.sandbox` →
`EvalContext.sandbox` to the evaluators and the batch prefetch. The runner
starts the child in its own process group and kills the group when the probe
exits or times out, so processes the target started neither survive nor hold
the output pipes open.

`dynamic.runner` starts a child interpreter (`python -s -B`, no `PYTHON*`
variable but `PYTHONHASHSEED=0`, wall-clock timeout, working directory set to the target root) and hands the cases to
`dynamic.probe` as JSON on stdin. The probe is a standard-library-only script:
it imports the target, calls it once per case, and writes one JSON result to stdout
while the target's own output is redirected to stderr. Import errors, timeouts,
and crashed interpreters come back as probe statuses rather than exceptions, so
one broken target cannot abort a multi-target run.

The probe never compares what a call returns; it reports what the code did,
through observers chosen per request (`observe`):

- `ImportRecorder` wraps `builtins.__import__`, `importlib.__import__`, and
  `importlib.import_module` before the target is imported and keeps each
  import whose calling frame lives under the target root; the probe's
  `imports` mode reports those made while the module loads
  (`forbid_runtime_imports`).
- `CallRecorder` installs a `sys.setprofile` hook for one call and records each
  call whose caller is code of the target's module and whose callee lives in
  another module, for Python functions (`call`) and C functions (`c_call`)
  alike (`forbid_runtime_calls`, `require_runtime_calls`). In `edges` mode
  it records every call between two different project modules instead
  (`enforce_reference_calls`).
- `WriteRecorder` wraps `__setattr__` of every class defined under the target
  root and, while a case runs, records assignments whose code object is not a
  method found along the object's class MRO (`forbid_foreign_writes`).
- `InstanceRecorder` wraps `__init__` of every class defined under the target
  root and records the outermost construction of each object together with
  the project frame that asked for it, from before a method's instance is
  built (`forbid_runtime_instantiation`).
- `LineRecorder` installs a `sys.settrace` hook for one call and records which
  lines of the target's own code run, for `details.coverage`.

Two paths use no observer. For a class target the probe does not call anything: `_inspect_class` reports
`inspect.isabstract` and the abstract methods, builds an instance from the
case unless told not to, and describes the requested members on it — where
each is found and, for protocol methods, whether its signature binds the
protocol's positional arguments (DYN005–DYN007). For the design-pattern
rules (DYN008) it also obtains a singleton twice and compares identity, or
subscribes a spy listener and notifies. A spy (`{"$spy": name}` in a case)
is a probe-made stand-in whose calls are collected in `_SPY_CALLS`, cleared
at the start of every case.

`_call_with_trace` serves runtime `enforce_flow`: it installs a `sys.settrace`
hook for one call and records the project functions called while each
statement labelled by a `flow` marker runs (reference) or every project
function called, in order (target). It records no values.

### Reporting

- `pythonarchtesting.report.api`
- `pythonarchtesting.report.ir`
- `pythonarchtesting.report.renderers`

Reporting converts run state into a stable report structure, then renders JSON
or Markdown.

### MCP Server

- `pythonarchtesting.mcp_server.server`
- `pythonarchtesting.mcp_server.evaluation`
- `pythonarchtesting.mcp_server.reports`
- `pythonarchtesting.mcp_server.markers`
- `pythonarchtesting.mcp_server.errors`

`mcp_server.server` registers seven tools and serves them on stdio
(`python-arch-test-mcp`). `.evaluation` runs `run_projects` and the report
generators exactly as the CLI does; `.reports` reads a saved `report.json`;
`.markers` reads the marker pages from `docs/markers` in a checkout, otherwise
from `share/pythonarchtesting/markers` (installed as data files, also looked up
under the user base for `pip install --user`); `.errors` holds `ToolInputError`.
Nothing outside the package imports `mcp`. See [mcp.md](mcp.md).

## Where To Extend Features

To add a new declaration-driven rule:

1. expose a marker in `pythonarchtesting.rules` and `pythonarchtesting.rules.declaration.core`
2. teach extraction and normalization to accept it
3. add a compiler in `pythonarchtesting.rules.compilation`
4. add an evaluator and register it in
   `pythonarchtesting.execution.evaluators.registry`
5. verify report output and docs

To change reporting behavior:

1. update report assembly in `pythonarchtesting.report.api` or `pythonarchtesting.report.ir`
2. update renderers in `pythonarchtesting.report.renderers`
3. keep JSON and Markdown expectations aligned
