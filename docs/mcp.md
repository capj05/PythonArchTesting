# MCP server

An optional [Model Context Protocol](https://modelcontextprotocol.io) server
is how a teacher's AI client drives the tool: it picks a principle from the
catalogue, prepares a task, evaluates the students' submissions and reads the
results by the principle's typical errors (the [workflow](#workflow) below).
The same server also lets the client author markers and check general
architecture; the general architecture tools (`describe_architecture`,
`check_architecture` and `propose_mapping`) are marked **Advanced** in the
table. It adds no logic of its own: every tool calls the same code as the
CLI. The server never edits reference or student files and never calls an
LLM. It writes only the run directory of `run_evaluation`, and in global mode
the self-task under `out_dir` (`prepare_global_task`) and the runs and
`global-report.json` under `output_dir` (`run_global_evaluation`), both outside
the submission; `verify_marker` and `prepare_task` work on temporary copies
they delete afterwards.

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
| `list_principles()` | yes | The teaching principles of the [catalogue](#principle-catalogue); each entry has `id`, `name`, `level` and `summary` (the first sentence of the principle's summary). |
| `describe_principle(principle_id)` | yes | One principle's full catalogue entry as JSON (below). An unknown id is a tool error listing the known ids, with close matches. |
| `prepare_task(task_dir, min_coverage=0.8, max_mutants=100, sandbox=None, sandbox_memory_mb=1024, config=None)` | no | Checks a [task](tasks.md) (`task.toml` beside an unannotated reference) before it grades a class. `problems`: what is wrong in `task.toml` (a role the principle's checks need left unbound, an unknown entity, missing cases, a reference with markers of its own); nothing runs while there are any. `checks`: per generated check its `role`, `entity`, `marker`, `cases_ran`, `coverage` (the share of the entity's lines its cases ran), `accepted` and `reasons`, judged as `check_cases` judges cases. `errors`: per typical error of the principle its `status`: `killed` (the error's mutation `operator` seeded it into copies of the reference, in the entities of the check that detects it, and the check failed on every copy; with `mutants`, `killed` and `signature_matched`, whether a mutant was also classified as that error), `survived` or `not_run` (with `survivors`), `no_mutants` (the operator finds something to change, but not in the entities of the check: a mis-bound role), `not_applicable` (the operator finds nothing to change anywhere in the reference, such as no public container; with `why`), `truncated` (`max_mutants` left the error no mutant; with `why`), `reference_fails` (the unchanged reference already fails the check that detects the error, so no mutant can count), `not_verifiable_by_mutation` (the error has no operator, or its operator cannot make the call its signature names; with `why` then) or `gap`. The unchanged reference runs every bound check even when no mutant was made. A static check (`forbid_private_access`) runs no cases and is not listed under `checks`. The operators take each parameter's class from the `$new` of the entity's cases. `accepted` when there are no problems, every check's cases are accepted, the unchanged reference passes (`reference_passes`; each check it fails is then listed under `problems` with its message, `<marker> fails on the reference: ...`), no mutant was cut (`truncated`) and every error with an operator is `killed` or `not_applicable`. Runs the reference sandboxed; writes nothing. |
| `discover_roles(submission, principles, assignment=None)` | yes | [Global mode](global_mode.md) (no reference: the submission is its own), step 1: per principle the entities that play its roles, found by code, `conflicts`, `not_applied`, and `cases_needed` (every entity a check runs, with what its cases must exercise); `syntax_errors`. Runs nothing. |
| `prepare_global_task(submission, principle, cases, out_dir, overrides=None)` | no | [Global mode](global_mode.md), step 2: the discovery after the AI's `overrides` (add, dispute, move), and the self-task written to `out_dir` (one per base for several polymorphism hierarchies): `principle`, `task_dirs` and `parts` (each with `task_dir`, `roles`, `conflicts`, `not_applied`, `dropped`, `problems`, and `base` when there are several; with one part its keys are repeated at the top level), `ignored_cases`, `syntax_errors`. `out_dir` must lie outside the submission. Runs nothing. |
| `run_global_evaluation(submission, task_dirs, output_dir, sandbox=None)` | no | [Global mode](global_mode.md), step 3: judges the submission by each task and writes `output_dir/global-report.json`: per principle its `status` (`violated`, `ok`, `unverified`, `not_applied`) and `unexercised` (the lines no case ran), the findings once across principles, `counts`, `submission`; the response adds `report_json`. Trusts each task's `discovery.json`: after the submission changes, prepare the tasks again. Runs the code sandboxed. |
| `validate_declarations(source, reference_modules=None, validation_scope="all", config=None)` | yes | The CLI's `--validate-declarations`: diagnostics for every marker in the reference. Runs no target code. |
| `check_cases(source, entry, cases, init=None, min_coverage=0.8, timeout_s=5.0, sandbox=None, sandbox_memory_mb=1024, config=None)` | no | Runs proposed `cases` of the reference function `entry` (`"module.function"`) on the reference, sandboxed. `accepted` when every case runs (an exception the reference raises on purpose is reported, not rejected) and the cases ran at least `min_coverage` of the entry's lines; `reasons`, `coverage.unexercised_lines` and the calls between modules the cases drove (`edges`) say what to change. Use before putting cases into a runtime marker, `architecture_entry` or a task's `[cases]`; for a [task](tasks.md), `source` is its reference directory (the task directory is a tool error). |
| `verify_marker(source, rule, operators=None, files=None, libraries=None, max_mutants=100, dynamic=False, sandbox=None, sandbox_memory_mb=1024, config=None, detail="problems")` | no | Seeds architectural violations into copies of the reference with named operators: `add_import` (a module imports a project module it did not), `lazy_import` (the same inside its first function), `add_library` (`import pickle`, or `libraries`), `dynamic_import` (`__import__("pickle")` at the top of a module's first function: an import by a computed name, which no static rule sees), `rebuild_injected` (a constructor builds its own collaborator of the injected one's class; the marker's `init` must inject real objects (`$new`): a `$spy` has no class to rebuild, and the mutant does not run), `drop_call` (a method no longer calls `self.<collaborator>.<method>(...)`: a call standing as a statement is removed, a call whose result is used is replaced by its first argument, or `None` without one), `use_private_name` (another module gets a private helper `_archtest_private`, and a module imports and calls it: two files change), `break_port` (a public method of a class takes a new required parameter, or is renamed), `foreign_write` (right after a method first reads `x.a` of an object other than `self`, or a module-level function of one of its parameters, it assigns `x.a = x.a`: the value stays, the write is foreign; one per object and function), `add_io_call` (a function or method first calls `print(...)`, `input()` or `open(...)`; one mutant per call), `mutate_private_container` and `mutate_public_container` (right after a function first calls a method of an object of a project class it got as a parameter, it changes the contents of that object's first private, or public, container: `obj._x["__archtest__"] = 0`, `obj._x.append(0)` or `obj._x.add(0)`, for a dict, list or set its class's `__init__` creates and never assigns anything else; one per object and function), `stub_role_call` (a function or method no longer calls the functions of one project module: each call's function becomes `(lambda *a, **k: None)`; one mutant per function and module), `add_io_via_helper` (a new module `_archtest_helper` prints in `say`, and a function or method imports and calls it first thing, on one line: output through a helper; two files change), `read_private_attribute` (a function first reads the first private data attribute of an object of a project class it got as a parameter: `_ = obj._x`; of an object a module global holds, `world.BAG`, right after the first statement that uses it; one per function), `add_builtin_call` (`add_io_call` generalised: also `isinstance(None, (object,)[0])` or `type((None,)[0]) == object` first thing, a branch on the type; one mutant per call), `drop_base` (a top-level class no longer names one of its bases, `object` excepted; one per class and base), `concretize_base` (an abstract top-level class loses `ABC`, `Protocol` or `metaclass=ABCMeta` from its bases and `@abstractmethod` from its methods; the `abc` import stays) and `hardcode_collaborator` (a constructor stores an object it builds, `self.x = C()`, in place of the collaborator it is given; `C` is the first class by name that can be built without arguments and is not abstract, never the constructor's own; unlike `rebuild_injected` it runs when `init` injects a `$spy`; `prepare_task` takes `C` from the modules of the detecting check, `verify_marker` from every project module and uses it only when named in `operators`). A name-mangled private attribute `__x` is written and read as code outside its class must, `obj._Owner__x`; a container is also one built by `defaultdict`, `Counter`, `OrderedDict`, a comprehension, a choice with a container branch (`x if x is not None else {}`) or a `@dataclass` field's `default_factory`. A [task](tasks.md) directory is no `source` here (a tool error): `prepare_task` verifies a task. `rule` (a marker name or a rule id prefix) must fail on each mutant (`killed`) and pass on the unchanged reference (`reference_passes`). Without `operators` only the operators the marker can see are used (import markers: the import operators and `dynamic_import`; `forbid_runtime_imports`: `add_library` and `dynamic_import`; `forbid_runtime_instantiation`: `rebuild_injected`; delegation and call markers: `drop_call` — for `require_runtime_delegation` only the calls to the collaborator its spy stands in for (the constructor parameter that receives the spy), and only of `member` when given; `module_interface`: `use_private_name`; `implements_protocol` and `implements_runtime_protocol`: `break_port`; `forbid_foreign_writes`: `foreign_write`, only in the methods (or classes) the marker is on; `forbid_private_access`: `read_private_attribute`; `subclass_of`: `drop_base`; `is_abstract_class`: `concretize_base`; a marker no operator can break, such as the pattern markers, needs `operators`). For `forbid_imports` and `forbid_runtime_imports` alone, the import operators import only what a marker of that file forbids, and `add_library` imports the libraries they forbid (`pickle` when none, or `libraries`); explicit `operators` or `libraries` are taken as given; without `files` only the files of the entities the marker is declared on (every file for a marker on the root package; for `use_private_name`, the mutants of other modules that reach past that file's module). `scope` says which were used. Only the rules `rule` names are evaluated. `by_operator` counts killed, survived and not-run mutants per operator; `case_gaps` lists, per runtime part, the lines of its code that no case ran on the reference (a violation there goes unseen; a survivor on such a line has `unexercised`); `skipped_files` (only when there are any) lists the files the operators could not read (`file`, `why`: it does not decode or parse), which get no mutant; `hints` says what survivors call for beyond the marker's arguments (an import by a computed name inside a function needs `forbid_runtime_calls`; case gaps need more cases, checked with `check_cases`); `mutants` lists the survivors and the mutants that did not run (`detail="all"`: every mutant). `accepted` when the reference passes, every mutant is killed and the sample was not cut (`truncated`). A survivor is a violation the marker misses or a change the architecture allows. A marker checked only at run time needs `dynamic=True`. The target must be one project: a directory holding several is evaluated as one and is not rejected. |
| `describe_architecture(source, mode="static", sandbox=None, sandbox_memory_mb=1024, config=None)` | no | **Advanced** (general architecture, not needed for a teaching task). The reference's architecture model, what `architecture_entry` compares a target with: `modules` (name, file), `static.imports` and `static.external` (each `edge` with the line that makes it, `at`), the `declaration` (`declared`, `policy`, `allow`, `forbid`, `ignore_external`, `ignore_type_checking`, and with a runtime part `entry`, `case_count`, `require_all`; without a declaration the defaults `--architecture` uses; a declaration that does not compile has only `declared` and `problems`, since no rule exists), and `compared`, when a target is compared with it at all (`static`: `always`, `with --architecture` or `never`, e.g. for a broken declaration or a reference that is no package; `runtime`: `with --dynamic` or `never`). `mode="full"` also runs the declared cases on the reference, sandboxed, and adds `runtime`: `calls`, `instances` (`"module -> module.Class"`), `external` (libraries the cases called), `libraries_compared` (what a target may call: those plus every library the reference imports), `coverage` and the cases' status. `status` is `completed` only when every case ran; otherwise (`reference_failed`, with `error`) the comparison would end in `ERROR` and judge nothing. Without `entry` and `cases`, or with a broken declaration, `reason` says why nothing ran. Edges are written as exceptions take them (`"a -> b"`, the package itself `__init__`). Libraries the declaration ignores and the markers' own package (`pythonarchtesting`, which the comparison counts as a reference library) are left out. `source` is resolved like the evaluation resolves it, since its last part is the package name. Describes, never judges; the CLI writes the same JSON with `--write-model`. |
| `run_evaluation(source, output_dir, targets=None, targets_dir=None, project_pattern=None, exclude_patterns=None, reference_modules=None, validation_scope="all", dynamic=None, sandbox=None, sandbox_memory_mb=1024, config=None, architecture=False, mapping=None, principle=None)` | no | Runs what the CLI runs (`architecture` is `--architecture`, `mapping` the content of a `--mapping` file) and writes `report.json` and the Markdown report into a new timestamped subdirectory of `output_dir`. Reports progress per target. Returns the summary of `summarize_report` plus `run_dir`, `report_json`, `report_markdown`, `config` (the file applied, or `defaults`), `runtime_rules_skipped`, `runtime_results_unverified` and `results_undecided` (results that passed with undecided architecture changes). `dynamic` left out means `False`. `principle` (a catalogue id) is checked before the run (an unknown id is a tool error) and echoed in the response, for `class_overview`. A principle's checks are runtime markers, which a static run SKIPS, so with `principle` a left-out `dynamic` becomes `True` and the response says so (`dynamic_forced: true`; `false` when the caller set `dynamic=True`); `dynamic=False` with `principle` is a tool error. `source` may be a [task](tasks.md) directory: its principle is then implied (another `principle` is a tool error), forces a dynamic run as above and is recorded in the report (`run.principle`). |
| `summarize_report(report_path, offset=0, limit=50, principle=None)` | yes | Totals (`exit_code`, `mode`, `source_path`, `targets_total`, `targets_failed`, `skipped_total`, `undecided_total`), rules ranked by number of failing targets (`rules`), a page of targets (`targets`: `target_id`, `display_name`, `exit_code`, `problems`). With `principle`, also `passed`, `failed` and `not_judged`, `by_error` (the number of targets per typical error, [below](#results-by-typical-error)), `not_judged_by_reason` (the number of not judged targets per reason), and on each target of the page its `verdict`, `errors` and, when it has any, its `not_judged` reasons. |
| `class_overview(report_path, principle=None, offset=0, limit=50)` | yes | The class by the typical errors of `principle` (left out: the principle the report records, from a task source; neither is a tool error): `submissions` and its split into `passed`, `failed` and `not_judged` ([below](#results-by-typical-error)), which add up to it; `by_error`, per error id that occurs (catalogue order, then the built-in `missing_required_entity`, `unclassified` last; [below](#built-in-error-ids)) its `count` of submissions, `title`, the submission names (`submissions`, at most 50) and `submissions_total`; `not_judged_by_reason`, the same per reason of the not judged submissions; and `submissions_page`, a page of submissions (`name`, `verdict`, `errors`, and `not_judged` reasons when it has any). The counts cover the whole report, only `submissions_page` is paged. |
| `check_architecture(source, target, mode="static", mapping=None, sandbox=None, sandbox_memory_mb=1024, config=None)` | no | **Advanced** (general architecture, not needed for a teaching task). One target against the reference, for an agent that fixes code in a loop: the same evaluation as the CLI with `--architecture` (and `--dynamic` in `mode="full"`), returned directly instead of written. `passed`, `complete` (false when a part was `SKIPPED`, e.g. runtime checks in static mode: the pass then holds only for what ran), `reference_problems` (markers of the reference that do not compile: fix the reference, not the target), `problems` (each with `feedback`, below), `undecided` changes, counts of `skipped` and `unpaired` results, and with a `mapping` the pairs `applied` and `refused` (with the reason). |
| `propose_mapping(report_path, target)` | yes | **Advanced**: the way to handle a renamed required entity (a `missing_required_entity` the submission has under another name). The reference entities one target left unpaired (the source of `required_target_missing`), each with its kind, matching status and best candidates in the target, plus an empty `mapping_template`, and `paired_by_name`, the pairs the matching made by name only (rule `unique_name` or `member_of_paired_class`; worth a look, a mapping replaces them). Propose pairs from it and pass them as `run_evaluation(mapping=...)`; see [reporting.md](reporting.md#assisted-pairing). |
| `explain_target(report_path, target, include_passed=False, offset=0, limit=20, principle=None)` | yes | The failing and warning results of one submission, with evidence and `feedback`. With `principle`, the submission's `verdict` (and its `not_judged` reasons) and `findings` instead of the results: each violation classified by a typical error, and each result without a verdict ([below](#results-by-typical-error)), paged by `offset`/`limit`, with `findings_total`; the `title`, `why` and `fix` of the typical errors on the page once, in `errors` keyed by `error_id`; with `include_passed`, `passed`, the passed results of the principle's checks (`rule`, `target`). |
| `explain_rule(report_path, rule, offset=0, limit=50)` | yes | One rule across all targets. |

## Workflow

A teaching task needs no markers:

1. Pick the principle the task practises with `list_principles` and
   `describe_principle`.
2. Write `task.toml` beside the unannotated model solution with the client's
   own file tools: the principle, which functions play each of its roles, and
   the cases of each ([Tasks](tasks.md)).
3. Run `prepare_task` and fix what it reports until `accepted` is true.
4. Evaluate the class with `run_evaluation(source=<task dir>,
   targets_dir=...)`; the run is dynamic, because the principle's checks run
   the code.
5. Read the result by the typical errors of the principle: `class_overview`
   for the class, then `explain_target(principle=...)` for one submission.
   Read `not_judged` submissions apart: they were not checked, not passed.
   For a `missing_required_entity` the submission may have under another
   name, pair it yourself and rerun with `mapping` ([Renamed
   entities](#renamed-entities)). A rule that fails
   almost every submission points to a wrong task rather than wrong students.

Markers written into the reference remain the way to state anything else:
find them with `list_markers` and `describe_marker`, edit the reference,
run `validate_declarations` after every change, check runtime cases with
`check_cases` and verify a marker with `verify_marker` (it must pass on the
reference and fail on every seeded violation it is meant to catch). Before
writing exceptions or feedback about the architecture, read the reference's
model with `describe_architecture` (advanced; `check_architecture` checks one
target against it directly). Without a principle, read a report with
`summarize_report`, then `explain_target` or `explain_rule`.

### Renamed entities

Pairing a renamed entity is the job of the client's AI, not of a heuristic in
the tool. A submission that renames a function the task binds (`take` to
`vezmi`) has no counterpart by name, and its name and body may differ enough
that no similarity measure finds it. The AI reads the submission's code,
decides which of its functions plays that role and passes the pair:
`run_evaluation(..., mapping={"pairs": {"actions.take": "actions.vezmi"}})`.
`propose_mapping` (advanced) is only a hint: it ranks candidates by name and
structure, may offer none, and lists every unpaired reference entity, also
those no role binds. The tool stays deterministic: the same mapping always
gives the same result.

## Principle catalogue

The catalogue of teaching principles ships with the package
(`pythonarchtesting/principles/catalog/<id>.toml`, read with
`pythonarchtesting.principles.load_catalog()`); every entry is validated on
load. Its texts are English: the AI client words them for the reader, in any
language. `describe_principle` returns:

- `id`, `name`, `level`, `summary`, `why`: the principle and why it matters;
- `roles`: the parts of a task's code the checks refer to (role -> generic
  description; what plays a role is set by the task);
- `checks`: per role, the `marker` that covers it (with `modules`, fixed dotted
  names such as `builtins.print`, `target_role`, a role whose entities' modules
  are also targets, and `transitive`, when the marker takes them) and what its
  `cases` must exercise (left out for a static marker, `forbid_private_access`,
  which runs nothing);
- `errors`: the typical errors, each with `id`, `title`, `why` and `fix`, and
  either `detected_by` (the marker that fails on it), `what`, `signature` and,
  optionally, `operator` (the mutation operator `prepare_task` seeds it with),
  or `gap` (a known miss). `what` is a template filled from a failed result:
  `{function}`, `{file}`, `{line}` (the target's function), from the fact of
  the violation (`details.facts`) `{caller}`, `{callee}`, `{module}`, `{class}`,
  `{attribute}`, `{change}`, `{fact_file}`, `{fact_line}`, `{expected_base}`,
  `{concrete_methods}`, `{creator}`, `{expected}`, and derived from it
  `{callee_short}` (`print()`, `input()`, `open()`, else `module.name()`),
  `{via_last}` (the helper a detour ends in) and `{via_first_line}` (the line
  the detour starts at). `signature` tells the error from the others of its
  marker: the first fact's `kind` (`call`, `missing_call`, `write`, `read`,
  `not_subclass`, `not_abstract`, `missing_delegation`, `instance`), the
  `callee` (`"module:name"`) of a call, the `change` (`assigned`, `mutated`,
  `deleted`, `bypassed`) of a write, `via` (the call took a detour through
  other code) and `private` (the attribute written starts with `_`). A
  signature matches a fact on the keys it declares; no two errors of one
  marker declare the same signature;
- `neutral`: changes unrelated to the principle, which must not fail;
- `gaps`: what the tool cannot check yet, and why;
- `placeholders` and `signature_keys`: the meaning of each placeholder of
  `what` and of each key of `signature`, so the entry reads on its own.

A field an item does not set is left out. `example/principles/` holds, per
principle, a [task](tasks.md) and one variant per error and neutral change;
`example/principles/verify.py` checks them against the catalogue.

## Results by typical error

`class_overview`, and `explain_target` and `summarize_report` with
`principle`, classify every violation by the principle's typical errors
(a `principle` other than the one the report records is a tool error)
(`pythonarchtesting.principles.classify_target`), deterministically: each fact
of a failed result (`details.facts`) is matched against the `signature` of the
errors whose `detected_by` is the failing marker; of the errors that match on
every key they declare, the one declaring the most keys wins (ties in catalogue
order). Only `FAILED` and `ERROR` results are looked at (`WARNING` is no
violation).

The principle's checks are runtime markers: a static run SKIPS them and judges
nobody, which is why `run_evaluation(principle=...)` runs dynamic. A submission
gets one of three verdicts:

- `failed`: it has a violation, a fact of a failed result, or a missing
  required entity (`missing_required_entity`, below). The violation is a
  typical error, or `unclassified` when no typical error's signature matches
  it (a genuine violation the catalogue does not describe). Each counts under
  its id in `by_error` (catalogue order, then `missing_required_entity`, then
  `unclassified`).
- `not_judged`: no violation, but a result gave no verdict on the code, or
  every result of the principle's checks was SKIPPED, or there is none. Such
  a result is a failure without facts or an `ERROR` result; its `reason` is
  `syntax_error` for a file of the submission that does not parse (below),
  `ambiguous_match` or `low_confidence_match` for a reference entity the
  tool paired with less than certainty (below), else the result's
  `details.reason` (`probe_import_error`, `case_setup_failed`, ...), else
  `error` or `no_facts`. A submission whose
  checks were all SKIPPED has the SKIPPED results' reason
  (`dynamic_checks_disabled`), and one without any result of the principle's
  markers `no_principle_checks`. These count under `not_judged_by_reason`, not
  under `failed` or `by_error`. Not judged is never a pass.
- `passed`: neither.

A failed submission can also have results without a verdict (one function
violates, another could not run); its row lists their reasons under
`not_judged`.

A finding has `error_id` and `what` (the error's template filled from the
target and the fact) for a classified violation, `error_id` `null` for an
unclassified one, and `error_id` `null` with `not_judged: true` and `reason`
for a result without a verdict; and `rule` (the rule id), `target` (the
entity, `module:qualname`; the reference's when the target has none), `text`
(the violation as the report states it, or the result's message; left out
when `what` states it) and `facts` (the fact). The error's `title`, `why` and
`fix` are in `explain_target`'s `errors`. A typical error the tool cannot
detect (`gap`) never appears: a submission making it passes.

### Built-in error ids

Two error ids are the tool's own, the same for every principle; no
catalogue error may take them (nor `unclassified`). Their `title`, `why` and
`fix` come with `explain_target`'s `errors` like a catalogue error's.

- `missing_required_entity`: a function, class or method the reference's
  rules require has no counterpart in the submission (the rules' results say
  `required_target_missing`, match status `unmatched`). The cases make
  entities required too: a class a rule's cases construct
  (`{"$new": "inventory.Inventory"}`) that the submission does not have
  (renamed `Sklad`, say) is this finding, not one `case_setup_failed` per
  rule. One finding per reference entity, however many rules require it,
  never one result per rule. It is a violation: the submission does not keep
  the assignment's protocol, so the verdict is `failed`. `facts`: `entity`
  (the reference entity as a mapping names it, `shop.sell`), `kind`, `file`
  and `line` (in the reference), `match_status` and `rules` (every rule that
  requires it); for a class the cases construct only `entity`, `rules` and
  `required_by` (every entity whose cases construct it, `shop:sell`).
  `target` is the reference entity (`shop:sell`). An entity the tool paired
  with less than certainty (match status `ambiguous` or `low_confidence`) is
  no such finding, since the submission may have it: it is not judged, with
  `reason` `ambiguous_match` or `low_confidence_match` and `facts.candidate`
  (the best candidate, `shop.prodej`), one finding per entity likewise; a
  mapping pairs it. When the submission has the entity under
  another name (translated, say `prodej` for `sell`), call
  `propose_mapping` for the submission, then rerun `run_evaluation` with
  `mapping={"pairs": {"shop.sell": "shop.prodej"}}`; the checks then judge
  the paired function.
- `syntax_error`: a file of the submission does not parse. Its findings are
  then the `syntax_error` ones and the violations found in the code the tool
  could read (a typical error or `unclassified`), without what may follow
  from the unreadable file: entities without a counterpart and checks that
  could not run. With such a violation the verdict is `failed`, `syntax_error`
  among its `not_judged` reasons; without one it is `not_judged` with
  `reason` `syntax_error` (also `not_judged: true` on the finding). `facts`: `file` (relative to the submission), `line`, `offset`
  and `message` (the compiler's). A syntax error in the reference is no such
  finding: it is `not_judged` with `reason` `error` on every submission.

### Beginner layouts

A submission is a package, `<ident>_<surname>`, one directory per student in
`targets_dir`. Two layouts a beginner who runs the code from inside the
directory often writes are evaluated as the package they mean:

- **No `__init__.py`.** Matching and the static rules see an empty
  `__init__.py` when the reference's root has one. The runtime probe imports
  the directory as a package (an empty stand-in for the missing file) when
  a module in it imports relatively up to it (`from .inventory import
  Inventory` directly in it, `from ..inventory import Inventory` in its
  `domain/`), whatever its name (`05capj_capsky` and `capj05-capsky`
  included, as on the static side); otherwise it puts the
  directory on `sys.path`, where absolute imports among its modules work as
  they do for the student, and a case's `{"$new": "inventory.Inventory"}`
  names the top-level module `inventory`.
- **A sibling module imported absolutely** (`from inventory import
  Inventory` in `capj05_capsky/shop.py`). The static rules already name it
  the package's module. The probe binds the name to the package's module
  (`capj05_capsky.inventory`), one module object, so the cases' `$new`
  objects and `isinstance` see the same classes. A sibling is never put in
  place of another module: not of a standard-library one
  (`sys.stdlib_module_names`, also one not importable on this platform), one
  already imported, or one the interpreter finds on its own path (an
  installed distribution). Such an absolute import gets the other module,
  unlike when the student runs the code from inside the directory: a
  `json.py` in the package is reachable only as `from . import json` or
  `capj05_capsky.json`, and `from json import VALUE` is an import error the
  result reports (`probe_import_error`). Renaming the module avoids it.

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
  import's `file` and `line`; for `forbid_cycles` each cycle; for
  `forbid_runtime_calls`, `require_runtime_calls` and `forbid_foreign_writes`
  each fact of `details.facts` (see [reporting.md](reporting.md#runtime-facts))
  with `text`, the violation it states; for other rules their violations, or
  the summary;
- `undecided`, when the result lists changes nothing decided.

