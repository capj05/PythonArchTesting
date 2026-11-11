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

A check `{ role, marker, modules, target_role, target_kind, transitive }`
becomes, for an entity bound to `role`, the declaration of

```text
marker(*modules, *<modules of the entities bound to target_role>,
       transitive=..., cases=<the entity's cases>, init=<its init>)
```

in that entity's body. For `io_separation` that is `forbid_runtime_calls(
"builtins.print", "builtins.input", "io", transitive=True, cases=...)` on each
function of `grades`, and `require_runtime_calls("grades", cases=...)` on
`app.main`: the declarations the example reference used to carry as markers.

`forbid_runtime_instantiation` is the exception to "modules": its
`target_role` gives the qualified names of the classes bound to that role
(`discounts.NoDiscount`), not their modules, so that the context may still
build other objects of the same module (a `Log` beside the strategies). A
bound interface (an abstract class or a `Protocol`, `strategy =
["discounts.Discount"]`) stands for the classes of the reference that
implement it: its subclasses and, for a `Protocol`, the classes defining every
method it declares. A class a submission builds that no reference class
matches (a strategy renamed `PercentOff`, or a new `HalfPrice`) counts when it
lives in the module of a bound class and looks like one: a bound class or an
interface of theirs is among its bases, or it defines a public method named
like one of theirs (`apply`). The reference cannot name it. A class of its own
that is no such class (a value `Money`, a dataclass, an exception), a class
of its own in another module, and a reference class the role does not bind
stay allowed. The likeness is by name only: a helper of that module that
happens to define a method named like a bound class's is counted (the
strategy catalogue's gap `unmatched_class_by_method_name`). A role that binds no class (strategies written as functions,
`strategy = ["adventure.take", "adventure.look"]`) leaves the check without
a target: no declaration is made, `prepare_task` lists the check as
`not_applicable` with `why`, and the error it detects (`hardcoded_strategy`)
is `not_applicable` too; nothing is a failure of the reference. When the
modules of those functions also define classes, `problems` carries a line
starting `WARNING:` that says so (the teacher may have meant the classes);
the task is still accepted.

With `target_kind = "class"` (default `"module"`) the check gets, instead of
the modules of the entities bound to `target_role`, the qualified name of the
one class bound to it: `subclass_of("shapes.Shape")` on every class bound to
`variant` when `base = ["shapes.Shape"]`. It is an error of the task when
that role binds several classes or none. A role a class marker covers
(`subclass_of`, `is_abstract_class`), or that a `target_kind = "class"`
check takes its class from, binds classes only: a function or a module there
is an error of the task (`[roles]`), and so is the target class bound among
the classes that must derive from it. In the catalogue `target_kind = "class"`
is for `subclass_of` only and takes no `modules`.

A static marker (`forbid_private_access`, `subclass_of`,
`is_abstract_class`) runs no code and takes no cases: its check has no
`cases` in the catalogue, and its declaration has none (`init` neither); a
role with only static checks needs no `[cases]` at all. For
`encapsulation` each client function gets `forbid_foreign_writes(cases=...)`
and `forbid_private_access()`; the cases in `task.toml` are those of the
runtime check.

## Errors

`task.toml` is checked as a whole and every problem is reported together:

- a role a check needs (its `role` or `target_role`) that `[roles]` leaves
  unbound, a role the principle does not have, a role bound to nothing; a
  `target_role` of a `target_kind = "class"` check that binds no class or
  several;
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
  reference, in the entities of the check that detects it: `add_io_call` and
  `add_io_via_helper` in the logic functions, `stub_role_call` in an io
  function, only for the calls into a module the check names, and
  `foreign_write`, `mutate_private_container`, `mutate_public_container` and
  `read_private_attribute` in the client functions; `add_builtin_call`
  (`isinstance(None, (object,)[0])` or `type((None,)[0]) == object`) in the client functions,
  `drop_base` in a variant class and `concretize_base` in the base class;
  `drop_call` cuts `self.x.m(...)`, and `self.x(...)` when the constructor
  stored a parameter in `x` (a function passed in); `hardcode_collaborator`
  replaces `self.x = p` (or `self.x: T = p`) only for a parameter `p` the
  task's `[init]` gives a spy, by a class bound to the check's `target_role`
  that can be built without arguments). A call-seeding error whose
  signature names no callee is seeded with the calls its check names.
  The operators that need
  an object of a project class take the class of each parameter from the
  `$new` the entity's cases build for it, and only without cases from its
  annotation or the one project class that has every method called on it
  (never when a builtin container or `str` has each of those methods too).
  They also reach an object a module global holds (`world.BAG` built by
  `BAG = Bag()`, `world.current_place` annotated `current_place: Place =
  None`; through the imported module, a name imported from it, or a global
  of the function's own module), so a client that gets only a list of words
  is seeded too. A container is a dict, list or set any method of the owner
  class or of its project base assigns to `self` (a game's `initialize()`,
  not only `__init__`), unless another method assigns it something else;
  the constructor's containers come first. `foreign_write` seeds only an
  attribute of the privacy the error's signature declares (`replace_attribute`:
  a private one), so a reference whose owners have no private data attribute
  gives that error `not_applicable`.
  A static check (`forbid_private_access`, `subclass_of`,
  `is_abstract_class`) runs no cases and is not listed
  under `checks`. An error counts as `killed` only when at least one mutant's
  failure is classified as that very error (`signature_matched`); a mutant
  the check catches as another error is counted in `killed_other`, and an
  error whose kills are all of that kind has the status `killed_other` and
  keeps the task from being accepted. An error whose operator finds nothing to
  change anywhere in the reference (say `mutate_public_container` in a
  reference whose classes have no public container) is `not_applicable`,
  with `why`, and does not keep the task from being accepted: the error was
  not verified by a mutant. An operator that finds something to change, but
  nothing in the entities of the detecting check, gives `no_mutants`, which
  does: the role is bound to other code than the one the error lives in. An
  error whose operator cannot make the call its signature names (`add_io_via_helper`
  only prints), or without a callee none of the calls its check names, is
  `not_verifiable_by_mutation`, with `why` naming them. A check that fails on
  the unchanged reference, or does not run on it (a case that cannot be set
  up), is a line of `problems` with its reason, and its errors are
  `reference_fails`.
  A mutant that changes a constructor (`hardcode_collaborator`) counts for
  a check on any method of its class: the method's cases build the object
  first. When the unchanged reference already fails the detecting check (its
  failure is in `problems`), no mutant counts as killed: the error is
  `reference_fails`, with `why`, and the task is not accepted.
  Known limit: a container the owner's constructor creates is assumed to stay
  a container; a subclass that rebinds it to something else in its own
  constructor is not seen, and its mutant may fail in another way.
  `run_evaluation(source=<task>)` implies the task's principle,
  runs dynamically and records the principle in the report (`run.principle`),
  so `class_overview(report_path)` needs no `principle`.
- `check_cases` takes the task's reference directory; `verify_marker` takes
  no task (`prepare_task` verifies one).

The examples are `example/principles/io_separation/`,
`example/principles/encapsulation/`, `example/principles/polymorphism/`
(roles bound to classes: `base`, `variant`) and `example/principles/strategy/`
(a method role with `[init]` injecting a spy; the `strategy` role binds the
classes `forbid_runtime_instantiation` forbids building);
`example/principles/verify.py` evaluates their variants with the task as the
source.

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

The pairing of a renamed entity is the teacher's AI's job, not a heuristic of
the tool: it reads the submission's code, decides which of its functions plays
the reference's role and passes the pair as `mapping` (see
[MCP § Renamed entities](mcp.md#renamed-entities)). `propose_mapping` is only a
hint: it ranks candidates by name and structure and may offer none for a
function whose name and body both differ.

A role bound to a whole module (`logic = ["actions"]`) also covers the
functions a submission adds to that module, which no case can run: the
`forbid_runtime_calls` check of every function of the module gets
`cover_module=True` and reads their bodies for `print`, `input` and `open`
([forbid_runtime_calls](markers/forbid_runtime_calls.md#functions-no-case-runs-cover_moduletrue)),
so a submission that renames one of the module's functions does not switch
the scan off; a call found by several checks is reported once.
A call through a helper of another module is not seen there, nor a call in a
method of a class the submission adds.
