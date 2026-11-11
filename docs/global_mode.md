# Global mode

Global mode checks the taught principles in a student's free-form project
(a text adventure, say) without a reference solution. The submission is its
own reference: the code finds where each principle should apply, the
teacher's AI client writes inputs that run that code, and the existing core
checks the submission against itself. The verdict is always the code's.

## Which mode

| Mode | When | Tools |
|---|---|---|
| With a reference ([tasks.md](tasks.md)) | A small, closed task: every student writes the same functions and classes, and the teacher has a model solution. | `prepare_task`, `run_evaluation`, `class_overview`, `explain_target` |
| Global | A free project: each student names and splits the code their own way, so there is nothing to pair a reference with. | `discover_roles`, `prepare_global_task`, `run_global_evaluation` |

Global mode checks `io_separation`, `encapsulation` and `polymorphism`;
`strategy` has no role discovery yet and is a tool error there.

Several principles in the mode with a reference are several task directories
sharing one reference (`reference = "../reference"` in each `task.toml`).

## The three tools

All paths are absolute. Entity names are relative to the submission root:
`actions` (a module), `actions.take` (a function), `ship.Cargo` (a class),
`ship.Cargo.load` (a method).

1. **`discover_roles(submission, principles, assignment=None)`** runs nothing.
   Per principle it returns the roles found by deterministic predicates over
   the code (each entity with `source = "code"` and `why`), `conflicts` (an
   entity that fits two roles) and `not_applied` (a role the principle cannot
   do without has no candidate, with the typical error that may hide it).
   `cases_needed` lists every entity a check runs, its `role`, `kind` and the
   catalogue's text of what its `cases` must exercise; a module bound as a
   whole stands for its public functions, each of which needs cases.
   `syntax_errors` lists the files that do not parse. `assignment` (the task
   text) is only echoed back as context for the AI.
2. **`prepare_global_task(submission, principle, cases, out_dir, overrides=None)`**
   runs nothing either. It repeats the discovery, applies `overrides` and
   writes the self-task to `out_dir`: `task.toml` (whose `reference` is the
   submission itself), `selftask.json` and `discovery.json`. `cases` maps an
   entity of `cases_needed` to its cases, in the case language of
   [tasks.md](tasks.md), written as JSON (`args`, `kwargs`, `stdin`,
   `{"$new": "ship.State"}`); an entry of `kind: "method"` needs the
   arguments of its object's constructor in each case,
   `"init": {"args": [...]}`. It returns `task_dirs` and `parts`, one entry
   per task written, each with its `task_dir`, `roles`, `conflicts`,
   `not_applied`, `dropped` (bound entities without cases: they are left out
   of the task and reported as unverified, never lost) and `problems` (what
   keeps the core from running the task); with one part its keys are repeated
   at the top level. Beside them, once for all parts, `ignored_cases` (cases
   no check runs, with the reason: an entity of a role checked only
   statically, a private function, a name the submission does not have) and
   `syntax_errors`. A
   principle that does not apply lists nothing as `dropped`, since nothing
   of it runs. A
   polymorphism discovery with several independent hierarchies gives one task
   per base in `out_dir/<base>` (each part names its `base`); pass every one
   of `task_dirs` on.
3. **`run_global_evaluation(submission, task_dirs, output_dir, sandbox=None)`**
   judges the submission by each task, running it sandboxed (`bwrap` by
   default, `limits` is weaker), and writes `output_dir/global-report.json`.
   Each run writes under `output_dir/runs/`. Each task may be given once,
   and one task per principle (and base). It trusts the roles of each
   task's `discovery.json` as `prepare_global_task` wrote them and does not
   discover them again: after the submission changes (a student's
   resubmission, a fix), run `prepare_global_task` again, or the roles and
   cases of the old code are checked against the new.

`out_dir` and `output_dir` must lie outside the submission and must not
contain it: a task or a copy written into the project would become part of
it.

## What discovery binds

The project's own tests are no part of the program a principle is about:
discovery skips every module named `test_*.py`, `*_test.py` or
`conftest.py`, and everything under a directory named `tests` or `test`.

For `io_separation`:

- `io` is every function or method that calls `input()`, and every entry
  point: a project function an entry block calls, or a method it calls on
  an object of a project class (`Game().run()`, or `game = Game()` and then
  `game.run()`). An entry block is an `if __name__ == "__main__":` block or
  a bare call at the top of a module (`main()` or `game.run()` at the
  bottom of the file, without the guard); it may call the function by
  name, imported with `from game import run`, or through a module alias
  (`game.run()` after `import game` or `import game as g`). A function or
  method that reads the keyboard through a pure input helper is `io` too,
  in any module: `ui.ask()` after `import ui`, `ask()` after `from ui
  import ask`, `line = self.ask()`. So a launcher `def main(): game.run()`
  makes `game.run` looping on `ui.ask()` `io`, not logic. A function of a
  module with io, or a method, that the io calls and that prints, reads no
  keyboard, returns no value and changes nothing (as below) but calls
  project code (`show_score()` printing `score(cmd)`) is `io` as well.
  A module that calls its entry point without the guard runs it when it
  is imported, and the probe imports it: such a game is `unverified`
  (`probe_import_error`) until the call is put under the guard.
- A pure input/output helper is in no role: an input helper (below) or an
  output helper (next item); neither dispatches anything, is an entry point
  or is held by a table (`ask()` returning `input("> ")`, `show(text)`
  printing it). It never calls the logic, so
  as `io` it would be reported for `logic_in_main`, and as `logic` for the
  input or output it exists to do. A function that reads the keyboard and
  calls nothing of the project is such a helper only when its module has an
  anchor (an entry point, or another `io` entity that is no such helper:
  one that reads the keyboard beside other code, or calls the helper) or
  has no logic at all (a lone `inputs.py` with `ask()`, or with `ask()` and
  `ask_yes_no()`). Otherwise it stays `io`, where the dispute below applies:
  an action `take()` asking `input("What? ")` beside the actions it belongs
  to, called by name from the game loop. The decision does not depend on
  the order of the functions.
- An output helper of the user interface, in no role, is one definition for
  every scope: a module-level function or a method, in a module with io or
  without (there only when the io calls it). It prints (or opens a file),
  does not read the keyboard, returns no value (no `return <expr>`), calls
  nothing of the project and changes nothing. A call of the project is one
  the code can resolve: a project function or class by its name or through
  a module alias, or a method of the object itself (`self.m(...)`); a call
  on another object (`state.items()`, `text.format()`) is no project call,
  whatever methods the project's classes have. Changing nothing means no
  `global` / `nonlocal`, and
  no store to or `del` of an attribute or an item, no `+=` and the like,
  and no call of a mutating method (`append`, `extend`, `insert`, `remove`,
  `pop`, `popitem`, `clear`, `update`, `add`, `discard`, `setdefault`,
  `sort`, `reverse`, the `deque` and in-place `set` ones), except on a
  local name whose every plain assignment builds an object the function
  owns (a literal, a comprehension, `list(...)` or `sorted(...)`, a string,
  arithmetic on such values). `x += v` is never what decides that: an
  accumulator `total = 0` then `total += PRICES[item]`, or `line = ""` then
  `line += " " + name`, changes nothing. The check sees aliases:
  `bag = world["bag"]` then `bag.append(item)` changes `world`, and so does
  `+=` or a mutating call on any name bound from a parameter, an attribute,
  an item or a global, directly or through another such name (`held = pack`
  then `held += [x]`), or from `min`/`max`/`sum`, which may hand back an
  object they were given.
  A print-only `display.py` or a `View.show()` is therefore user interface,
  and an action that prints its result instead of returning it but changes
  the game state (`print_instead_of_return` in a `take()` that moves the
  item, as a function, a method of a model class or beside the game loop in
  one module) stays logic and is checked.

  The limitations: a `look()` that only prints the state and changes
  nothing is user interface, so it is not checked for
  `print_instead_of_return`; and a user interface function that empties a
  buffer it was given after printing it (`messages.clear()` in a
  `flush(messages)`) changes its argument, so it is logic and reported for
  `print_instead_of_return` although it is UI.
- `logic` is what the io code calls directly: a module whose functions it
  calls (or holds in a table such as `COMMANDS`, defined in the io's module
  or imported from another project module, `from commands import COMMANDS`
  or `commands.COMMANDS`) is bound whole; in a module
  with io or a pure helper, each function it calls is bound on its own; a
  method it calls or dispatches is bound by its name, and `self.m` only
  within the io method's own class, its bases and subclasses. What the logic
  calls in turn (a `rules` module behind `game`) is covered by the logic
  check, which follows calls. An abstract method, and every method of an
  abstract class (`ABC`, an `@abstractmethod`), is never bound to a role
  that runs code (`logic`, or a `client` of `encapsulation`): no case can
  build its object.

For `polymorphism`, a `client` is a function or method outside the
hierarchy that calls a polymorphic method of the base on an object
(`[i.use() for i in items]`). A method is polymorphic when a class of the
hierarchy declares it abstract (`@abstractmethod`, a body that only raises
`NotImplementedError` or is `...`) or two of its classes define it (the
base's own and an override); calling a method of the base no variant
overrides is no use of the hierarchy. The object is never `self`, and never
one that is obviously builtin: a literal or a comprehension, the result of
`dict(...)`, `list(...)`, `set(...)`, `str(...)`, `sorted(...)`,
`defaultdict(...)`, `Counter(...)` or `deque(...)`, a name all of whose
assignments are such values (in the function, or at the top of the module
when the function neither assigns it nor takes it as a parameter), or
`self.a` all of whose `self.a = ...` in the class are (`self.scores = {}`).
So `scores.update(extra)` does not make a client beside a base with
`update()`. The limitation: a parameter may be anything, so
`merge(scores, extra)` calling `scores.update(extra)` is still a client
when the hierarchy overrides `update()`.

## What the AI client may do

The AI finds the principle in the project and writes the inputs that run it;
the code decides. An override is
`{"entity", "role", "action", "why", "to_role"}`, and `action` is one of:

- `add`: bind an entity the predicates missed (`source = "ai"`);
- `dispute`: doubt a candidate. It stays bound and checked; its findings are
  flagged `role_disputed` with the reason, and the teacher decides. A
  candidate is never removed, since that would remove its checks;
- `move`: only from `io` to `logic` of `io_separation`, for a game action
  that reads the keyboard; accepted only when other code of the project
  refers to it (an entry point or a dispatcher calls it).

The code cannot tell a game action that reads the keyboard
(`input_in_logic`) from a user interface. A function that calls `input()` is
therefore bound to `io`, and disputed
(`disputed = "possibly input_in_logic: ..."`, source `code`) when it looks
like an action, that is when all of these hold:

1. it is no game loop and no dispatcher: it reads the keyboard in no loop
   and calls nothing it looked up in a table such as `COMMANDS`;
2. it is the only `io` function of its module, and the module has logic;
3. the project refers to it outside its own body and an entry block
   (resolved through the imports for a module-level function: `actions.take`
   or `take` after `from actions import take`, not any `x.take`).

A disputed function keeps the principle from being `ok` until the AI moves
it to `logic` (if the assignment makes it an action) or the teacher decides.
Its own missing call into the logic (`logic_in_main`) is
`missing_call_role_disputed` in `unverified`.
The limitations: an action that reads the keyboard inside a user interface
module, in a single-file game, or as a method of the same class as the game
loop is not disputed automatically; the AI can still `move` it. An input
helper alone in its module (`inputs.py` with only `ask()`, or `ask()` and
`ask_yes_no()`) is a helper in no role, so such a project can be `ok`; one
beside logic (`inputs.py` with `ask()` and a `parse()` the io calls) stays
`io` and is disputed, so the project is `unverified` until the teacher
decides. Two actions that read the keyboard in one module beside logic are
both `io` and neither is disputed (neither is the only `io` of its module);
their missing calls into the logic make the principle `unverified`
(`missing_call_role_dependent`), never `ok` and never `violated`, until the
AI moves them to `logic`.

An override the rules do not allow, or one naming an entity the submission
does not have, changes nothing and is listed in `conflicts`.

Weak or wrong cases can only make something go unfound, which shows as
`unverified`; they cannot make a finding up, since the probe records only
what really ran.

## Statuses

| Status | When |
|---|---|
| `not_applied` | A role the principle cannot do without has no candidate (no owner class, no base class). |
| `violated` | The run or a static marker found a typical error of the principle (`findings`). No mutant runs: the finding is proof in itself. |
| `ok` | No finding, the cases cover at least 80 % of every checked entity, and every typical error that a mutation operator can seed is caught (`killed`, or `not_applicable` / `gap`). |
| `unverified` | No finding, but that is not proven. `unverified` lists why: low `coverage`, a mutant that `survived` or did not run, a result without a verdict (a case that timed out, `probe_timeout`), an entity without cases (`no cases`), a problem of the `task`, a file that does not parse (`syntax_error`), a bound entity whose role is disputed (`role_disputed`, with the doubt as `why`), an io entity that called the logic in some of its cases but not in others (`missing_call_in_some_cases`), or any other missing call of an io entity into the logic (`missing_call_role_dependent`, or the more specific `missing_call_self_calls_unobserved` and `missing_call_role_disputed`, below). |

A missing call into the logic (`logic_in_main`) is never `violated` in
global mode: whether the io should call that module depends wholly on which
entities discovery took for io and logic. The finding is `unverified` (with
the entity, `error` and `module`) and no mutant runs; its reason is the most
specific one that applies:

- `missing_call_in_some_cases` (with the `cases` that missed it and
  `case_count`): another case of the entity did call the module (a case
  that quits at once calls no logic);
- `missing_call_role_disputed`: discovery disputed the io entity as an
  action that may read the keyboard;
- `missing_call_self_calls_unobserved` (with the `logic` methods): the run
  does not record a call a method makes to a method of its own object
  (`self.handle(line)`), and the io method's class, or a project base or
  subclass of it, has a method bound to `logic`;
- `missing_call_role_dependent`: any other missing call.

The cost: a `main` that truly never calls its logic is `unverified`, not
`violated`.

`unexercised` lists, for every status, `ok` included, the lines of each
checked entity that no case ran (`entity`, `file`, `lines`): nothing
checked them, and an `ok` says nothing about them.

A submission with a file that does not parse is `unverified` for every
principle, with `file`, `line` and `why`; nothing of it runs. A case that
never ends (a game loop no input ends) is stopped after the marker's timeout
of 5 s and makes the principle `unverified`; no mutant runs then, since each
would run into the same loop.

`unclassified` lists violations no typical error explains (a write to a
project object of another kind, say): shown to the teacher, but they never
make a principle `violated`.

## The report

`global-report.json` has one entry per principle (per base for several
polymorphism hierarchies) under `principles`, the `findings` of all of them
once more, deduplicated across principles (two findings of different
principles are one when their facts are equal apart from which case saw
them, `case`, `cases`, `via`, `origin_line`, and name a file and a line;
findings of one principle are never merged), each with the `principles` it
was found under, and `counts` per status. Shortened, for the `space_a` test fixture:

```json
{
  "principles": [
    {
      "principle": "io_separation",
      "status": "violated",
      "roles": {
        "logic": [{"entity": "actions", "source": "code", "why": "..."}],
        "io": [{"entity": "ui.main", "source": "code", "why": "..."}]
      },
      "sites": 6, "ok": 5, "violations": 1,
      "findings": [{"error_id": "print_instead_of_return", "target": "actions:status",
                    "what": "Function `status` (actions.py:18) prints to the screen: ...",
                    "facts": {"kind": "call", "callee": "builtins:print",
                              "file": "actions.py", "line": 19}}],
      "coverage": null, "unverified": [], "mutation": null, "unclassified": [],
      "unexercised": [{"entity": "actions.load", "file": "actions.py", "lines": [11]},
                      {"entity": "ui.main", "file": "ui.py", "lines": [12, 13, 16]}]
    },
    {
      "principle": "polymorphism",
      "status": "ok",
      "roles": {
        "base": [{"entity": "ship.Module", "source": "code",
                  "why": "abstract class with subclasses"}],
        "variant": [{"entity": "ship.Reactor", "...": "..."},
                    {"entity": "ship.SolarPanel", "...": "..."}],
        "client": [{"entity": "actions.total_power", "source": "code",
                    "why": "calls power() of ship.Module on an object"}]
      },
      "sites": 4, "ok": 4, "violations": 0, "findings": [],
      "coverage": 1.0, "unverified": [],
      "mutation": {"type_switch": "killed", "type_comparison": "killed",
                   "not_a_subclass": "killed", "concrete_base": "killed"},
      "unclassified": [], "unexercised": []
    },
    {
      "principle": "encapsulation",
      "status": "violated",
      "roles": {"owner": [{"entity": "ship.Cargo", "source": "code",
                           "why": "creates list _crates in __init__, changed by load()"}],
                "client": ["..."]},
      "sites": 9, "ok": 8, "violations": 1,
      "findings": [{"error_id": "bypass_method", "target": "actions:take",
                    "facts": {"kind": "write", "class": "Cargo", "attribute": "_crates",
                              "file": "actions.py", "line": 3}}],
      "coverage": null, "unverified": [], "mutation": null, "unclassified": [],
      "unexercised": ["..."]
    }
  ],
  "findings": [
    {"error_id": "print_instead_of_return", "...": "...", "principles": ["io_separation"]},
    {"error_id": "bypass_method", "...": "...", "principles": ["encapsulation"]}
  ],
  "counts": {"not_applied": 0, "ok": 1, "unverified": 0, "violated": 2},
  "submission": "/path/to/space_a"
}
```

`sites` counts the bound entities with a check and `violations` those with a
finding. `mutation` maps each typical error to the status of its mutation
check, `null` when no mutant ran (a violated principle). A finding carries
the catalogue's `title`, `what`, `why` and `fix`; the AI words the feedback
for the student from them.
