# Tasks

A **task** checks one principle of the [catalogue](mcp.md#principle-catalogue)
in a class's submissions without any marker in the model solution. It is a
directory with `task.toml` and the unannotated reference:

```
<task>/
  task.toml       the principle, its roles bound to the reference, the cases
  reference/      the model solution, a package without markers
```

The tool turns each check of the principle (`[[checks]]` of its catalogue
entry) into the declaration a marker would give, for every entity bound to the
check's role, with that entity's cases, and compiles it with the same
compilers as a marker read from source. The reference files are never changed.

## `task.toml`

```toml
principle = "io_separation"   # a catalogue id (list_principles)
# reference = "reference"     # optional: the reference directory, relative to the task

[roles]
logic = ["grades"]            # a module: its top-level public functions
io = ["app.main"]

[cases]
"grades.parse_grades" = [{ args = ["1 2 3 1"] }, { args = ["1 x 7"] }]
"grades.average" = [{ args = [[1, 2, 3, 1]] }, { args = [[]] }]
"grades.format_summary" = [{ args = [[1, 2, 3, 1]] }]
"app.main" = [{ args = [], stdin = "1 2 3 1\n" }, { args = [], stdin = "1 x\n" }]

# [init]                      # optional, per method: how to build `self`
# "shop.Shop.sell" = { args = [] }
```

- `[roles]` binds every role of the principle to entities of the reference,
  as `"module.function"`, `"module.Class.method"`, `"module.Class"`, or
  `"module"`, which stands for the module's top-level public functions (not
  those starting with `_`, not methods). A role no check refers to (such as
  `owner` of `encapsulation`) may be left out.
- `[cases]` gives every entity a check covers its cases, keyed by its dotted
  name (a module's functions each by their own name). The cases use the case
  language of the runtime markers ([dynamic-checks.md](dynamic-checks.md)):
  `args`, `kwargs`, `init`, `steps`, `stdin`, and objects built with
  `{ "$new" = "module.Class", args = [...] }`. What they must exercise is the
  check's `cases` text in `describe_principle`.
- `[init]` gives a method the construction of its `self`, as a marker's
  `init=` does.
- One `[cases]` entry per entity is shared by every check on that entity: a
  principle with two checks of one role runs both on the same cases, so they
  must exercise what each check's `cases` text asks for.

TOML 1.0 keeps an inline table on one line; an array of them may span lines,
and a key with characters other than letters, digits, `_` and `-` is quoted
(`"$new"`, `"hruška"`). Only strings, numbers, booleans, arrays and tables are
cases: a TOML date is an error.

## What a check becomes

A check `{ role, marker, modules, target_role, transitive }` becomes, for an
entity bound to `role`, the declaration of

```text
marker(*modules, *<modules of the entities bound to target_role>,
       transitive=..., cases=<the entity's cases>, init=<its init>)
```

in that entity's body. For `io_separation` that is `forbid_runtime_calls(
"builtins.print", "builtins.input", "io", transitive=True, cases=...)` on each
function of `grades`, and `require_runtime_calls("grades", cases=...)` on
`app.main`: the declarations the example reference used to carry as markers.

## Errors

`task.toml` is checked as a whole and every problem is reported together:

- a role a check needs (its `role` or `target_role`) that `[roles]` leaves
  unbound, a role the principle does not have, a role bound to nothing;
- an entity the reference does not have (the message lists up to five
  closest names the reference has), a module without public functions;
- an entity a check covers without `[cases]`, and cases or init of an entity
  no check covers;
- cases the compiler of the check's marker would refuse: an empty list, a case
  that is not a table, an unknown key (such as `expected`), and a `nan` or
  `inf` anywhere in them;
- an unknown key, an unknown principle, a missing reference directory;
- a reference that carries markers of its own. A task's reference must be
  unannotated, so that what is checked is exactly what `task.toml` says;
  evaluate a reference with markers without `task.toml`.

The CLI prints them as one error and exits 2; `prepare_task` lists them under
`problems`, together with every error or warning the compiler gives for the
generated declarations (a `compiler_invalid_param`, with the entity and the
reason), so a task that is not accepted always says why; `run_evaluation`
returns them as a tool error.

## Using a task

- CLI: `python-arch-test --source <task> --targets-dir <submissions> --dynamic`.
  A `--source` without `task.toml` is a reference as before.
- MCP: `prepare_task(task_dir)` validates the task, runs the cases of every
  check and verifies by mutation that the checks catch the principle's typical
  errors (an error's `operator` in the catalogue seeds it into copies of the
  reference). An error counts as `killed` only when at least one mutant's
  failure is classified as that very error (`signature_matched`); a mutant
  the check catches as another error is counted in `killed_other`, and an
  error whose kills are all of that kind has the status `killed_other` and
  keeps the task from being accepted. `run_evaluation(source=<task>)` implies the task's principle,
  runs dynamically and records the principle in the report (`run.principle`),
  so `class_overview(report_path)` needs no `principle`.
- `check_cases` takes the task's reference directory; `verify_marker` takes
  no task (`prepare_task` verifies one).

The examples are `example/principles/io_separation/` and
`example/principles/encapsulation/`; `example/principles/verify.py` evaluates
their variants with the task as the source.

## Pairing the entities a role binds

The assignment prescribes the names of the entities `[roles]` binds (the
functions of a bound module, a bound function, method or class): a
submission is expected to keep them. Such an entity is paired only with a
submission entity of the same qualified name (in any module, as pairing by
name allows) or by an explicit `mapping`; never by structure or similarity
alone. So a submission that renames `sell` to `prodej` has no `sell`: the
finding is `missing_required_entity`, even when another of its functions
(say a helper `odeber` whose body is the reference's one line
`inventory.remove(...)`) looks like `sell`. When the rename is legitimate,
`propose_mapping` lists the candidates and `run_evaluation(mapping=...)` with
`{"pairs": {"shop.sell": "shop.prodej"}}` pairs them; the checks then judge
`prodej`. Entities no role binds keep the usual matching by name, structure
and similarity.
