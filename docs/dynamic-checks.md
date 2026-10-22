# Dynamic checks (`--dynamic`)

Static analysis reads the target's source. Some structural facts are not in
the source, though: which object an injected parameter will hold, which module
a name passed to `importlib` resolves to, which code ends up assigning an
attribute. The runtime rules answer those questions by running the target in
a separate interpreter and watching it.

They check **how the program is built, never what it computes.** A rule's
`cases` only give call arguments that make the code run; no rule compares a
return value or the state a call leaves behind. Two targets that compute
different results but are layered the same way get the same verdict.

## Rules

| Rule | Marker | Question it answers |
|------|--------|---------------------|
| `DYN001` | [`forbid_runtime_calls`](markers/forbid_runtime_calls.md) | Does code of this module call into a layer it must not reach? |
| `DYN001` | [`require_runtime_calls`](markers/require_runtime_calls.md) | Does it delegate to the layer it must go through? |
| `DYN001` | [`enforce_reference_calls`](markers/enforce_reference_calls.md) | Does the whole module-to-module call graph stay within the reference's? |
| `DYN002` | [`forbid_runtime_imports`](markers/forbid_runtime_imports.md) | Which modules does importing it pull in, including by computed name? |
| `DYN003` | [`forbid_foreign_writes`](markers/forbid_foreign_writes.md) | Are objects' attributes assigned, deleted, or their containers changed only by their own class (encapsulation)? |
| `DYN004` | [`forbid_runtime_instantiation`](markers/forbid_runtime_instantiation.md) | Does the code receive its dependencies instead of creating them (dependency injection)? |
| `DYN005` | [`require_runtime_members`](markers/require_runtime_members.md), [`forbid_runtime_members`](markers/forbid_runtime_members.md) | Which members does a built instance really have, dynamic attributes included? |
| `DYN006` | [`is_runtime_concrete_class`](markers/is_runtime_concrete_class.md), [`is_runtime_abstract_class`](markers/is_runtime_abstract_class.md) | Is the class abstract or instantiable as Python decides it, external bases included? |
| `DYN007` | [`implements_runtime_protocol`](markers/implements_runtime_protocol.md) | Does a built instance satisfy a protocol, wherever its members come from? |
| `DYN008` | [`is_runtime_singleton`](markers/is_runtime_singleton.md), [`enforce_runtime_observer`](markers/enforce_runtime_observer.md), [`require_runtime_delegation`](markers/require_runtime_delegation.md) | Does the code behave as the design pattern requires — one shared instance, notified listeners, delegation to an injected strategy? |
| `FLW002` | [`enforce_flow(..., cases=...)`](markers/enforce_flow.md#runtime-check-with-cases) | Does the function run the reference's processing stages (the project functions each calls) in order? |

Without `--dynamic` every one of them is reported as `SKIPPED` and does not
affect the exit code, so a reference that carries them still works for static
runs. Because such a run would otherwise read as a pass, the CLI then prints
`warning: N runtime rule result(s) were SKIPPED because --dynamic was not
given` on stderr. The report's `run.mode` (and the Markdown header's
**Mode**) says `static-only` or, with `--dynamic`, `dynamic (sandbox: ...)`.
`--sandbox` and `--sandbox-memory-mb` are rejected without `--dynamic`, and
`--dynamic` is rejected with `--validate-declarations`, which runs no code.

A passing runtime result whose check left something out (lines no case ran,
flow stages that could not be recognised, reference calls the target never
made, a case that stopped at an exception) carries that in its message,
`OK: <summary>`, instead of a bare `OK`, and lists it in `details.unverified`
([What a pass means](#what-a-pass-means)).

```bash
python-arch-test --source example/rule_showcase/dyn001_layers/reference \
    --targets-dir example/rule_showcase/dyn001_layers/assignments \
    --format json --dynamic --sandbox bwrap
```

### Runtime counterparts of static rules

The static rules read the class body; several of them document what that
cannot see — attributes created in a loop or by `__dict__.update`, abstract
methods of bases outside the project, protocol members attached at run time.
DYN005–DYN007 check the same contracts on the object Python actually builds.
They do not replace the static rules, which need no execution and also cover
code no case reaches; use both where the target may build its classes
dynamically.

| Static rule | Runtime counterpart |
|-------------|---------------------|
| [`required_attribute`](markers/required_attribute.md), [`require_member_set`](markers/require_member_set.md) | [`require_runtime_members`](markers/require_runtime_members.md) |
| [`does_not_have`](markers/does_not_have.md) | [`forbid_runtime_members`](markers/forbid_runtime_members.md) |
| [`is_concrete_class`](markers/is_concrete_class.md) | [`is_runtime_concrete_class`](markers/is_runtime_concrete_class.md) |
| [`is_abstract_class`](markers/is_abstract_class.md) | [`is_runtime_abstract_class`](markers/is_runtime_abstract_class.md) |
| [`implements_protocol`](markers/implements_protocol.md) | [`implements_runtime_protocol`](markers/implements_runtime_protocol.md) |
| [`forbid_imports`](markers/forbid_imports.md) | [`forbid_runtime_imports`](markers/forbid_runtime_imports.md) |

## Cases

Rules that call a function or method, or build an instance of a class, take
`cases`, a non-empty list of dicts with only these keys (for a class, `args`
and `kwargs` go to its constructor):

| Key | Meaning |
|-----|---------|
| `args` | Positional arguments, a list. |
| `kwargs` | Keyword arguments, a dict with string keys. |
| `init` | Methods only: `{"args": [...], "kwargs": {...}}` for constructing the instance; overrides the rule-level `init`. Static and class methods are called without an instance. |
| `steps` | Methods and classes only: other methods of the same instance called first, in order, to bring it into the state the case needs — `[{"call": "add_item", "args": [...], "kwargs": {...}}]`. For a method they run before the observed call and are not observed themselves; for a class they run after construction, before the instance is inspected. A step that raises means the case could not be set up. Not for `is_runtime_singleton`. |

Values must be JSON literals (numbers, strings, booleans, `None`, lists, dicts
with string keys). `{"$spy": "name"}` passes a recording stand-in that accepts
any call ([`require_runtime_delegation`](markers/require_runtime_delegation.md#the-spy));
`{"$spy": "repo", "returns": {"find": ...}}` makes `repo.find(...)` return the
given value (built like any case value), so code that queries a collaborator
keeps running. An object is built with `{"$new": "Name", "args": [...],
"kwargs": {...}}`; `Name` is looked up in the target module, or as
`module.Name` in the target package, so the target's own classes are used.
This is how a controller gets its service injected:

```python
{"args": [{"id": "A1"}, {"$new": "service.OrderService",
                         "args": [{"$new": "repository.OrderRepository"}]}]}
```

Names in cases are the reference's. When the matching step paired a
reference class or method with a target one of another name or module, the
target's name is used: `{"$new": "repository.OrderRepository"}` builds the
target's `storage.OrderRepository`, and a step calling `add_item` calls the
target's `add` when the two methods were matched.

A function that is a coroutine (`async def`) or a generator only creates an
object when called; the probe runs it to the end (`asyncio.run`, or by taking
up to 10,000 items), so its body is observed.

Pick cases that drive the code through the paths whose structure matters. An
exception the call raises is recorded (`details.cases[i].raised`) but is not a
failure by itself: whatever the code did before raising is still judged.

## How it runs

1. The target entity is found by the normal matching step, so a target that
   renamed a parameter or moved a helper is still matched.
2. A fresh interpreter is started with `python -s -B` (no user site-packages,
   no `__pycache__` written) in an environment without any `PYTHON*` variable
   (no `PYTHONPATH`, no `PYTHONSTARTUP`) except `PYTHONHASHSEED=0`, working
   directory set to the target root. A target root that contains `__init__.py`
   is imported as a package, so its relative imports work.
   The fixed hash seed, and `random` seeded alike before the target is
   imported and before every case, make two runs of the same target observe
   the same calls in the same order: iterating a set of strings, or shuffling,
   cannot change a verdict from one run to the next.
3. All call, write, instantiation, and class rules on the same target module
   run in one interpreter,
   each bounded by its own `timeout_s` (on platforms with `signal.setitimer`);
   the time spent importing the module is charged to every rule, as it would
   be in an interpreter of its own, and a deadline swallowed by a bare
   `except:` in the target still counts as a timeout. Each rule's output is
   reported with that rule only. If the shared run as a whole times out or
   crashes, every rule is re-run in its own interpreter.
4. The child imports the target module, runs the cases with the requested
   observers, and returns one JSON result. Anything the target prints goes to
   stderr and is kept as `details.stderr_tail`.
5. A rule is `FAILED` with `details.reason` set to `violation`,
   `case_setup_failed` (an argument or the instance could not be built),
   `probe_import_error`, `probe_timeout`, or `probe_crashed`. When a case
   cannot be set up for the target, it is tried on the reference too; if it
   fails there as well, the case itself is wrong and the rule is `ERROR`
   (`reference_case_invalid`) instead, so a broken reference does not fail
   every student.
6. Rules that compare the target with the reference
   ([`enforce_reference_calls`](markers/enforce_reference_calls.md), runtime
   [`enforce_flow`](markers/enforce_flow.md#runtime-check-with-cases)) and the
   re-run of a case that could not be set up run the reference once per run:
   with `--targets-dir`, every target is compared with the same outcome
   instead of starting the reference again for each one.

## What a pass means

A runtime rule sees only the code its cases execute, so `OK` means "no
violation on the paths that ran", not "no violation anywhere". The probe
therefore records which lines of the target function or method ran (its own
body, and the functions, lambdas and comprehensions nested in it, but not the
helpers it calls) and the result says what was left out:

- `details.coverage` holds `file`, `lines_total`, `lines_run`, and
  `unexercised_lines`, the lines no case ran.
- When that list is not empty, the summary of a passing rule ends with
  `no case ran lines 16-18 of bank.py, so they were not checked`. Add a
  case that reaches those lines (an error path, the other branch) to
  check them too.
- When a required call or delegation is missing, the violation names the
  lines that did not run in that case (`; lines 12-14 did not run in this
  case`). That tells a call the code never makes apart from one it would
  make on a path the case did not take.

Line coverage is not recorded for runtime `enforce_flow`, whose stage tracing
uses the same interpreter hook, or for rules on classes.

Every passing result that left something out lists why in
`details.unverified`, as stable codes:

| Code | Left out |
|------|----------|
| `unexercised_lines` | Lines of the target no case ran. |
| `unchecked_stages` | Flow stages that call no project function and could not be recognised. |
| `reference_calls_not_made` | Edges of the reference the target never made (without `require_all`). |
| `case_raised` | A case stopped at an exception; the summary names the case and the exception. |

The status stays `OK` and the exit code is unchanged, but such a pass is not
a clean one: the CLI prints `warning: N runtime rule result(s) passed with
code or cases left unchecked` on stderr, the report's results summary counts
them in `unverified_total` (**Passed With Unchecked Code** in Markdown), and
the MCP server's `run_evaluation` returns `runtime_results_unverified`.

## Limits common to all runtime rules

- Example-based: only the paths the cases execute are observed; see
  [What a pass means](#what-a-pass-means).
- Calls and line coverage follow the main thread and the threads the target
  starts with `threading` while a case runs. The case then waits up to one
  second for those threads (daemon threads excepted) to finish; what a thread
  does after that is not observed. Threads that existed before the case, and
  other processes, are not observed. Attribute writes, instantiation, and spy
  calls are recorded from any thread.
- A target root without `__init__.py` whose module shares a name with a
  standard-library module the runner itself imports (`json`, `os`, `math`, `random`,
  `inspect`, `traceback`, ...) resolves to the cached standard-library module.
  Make the root a package or rename the module.

## Security

Target code runs with your user's permissions, confined by `--sandbox`:

| Mode | Confinement |
|------|-------------|
| `none` | A separate process with a wall-clock timeout; it inherits your environment. |
| `limits` (default) | Plus: data memory (`RLIMIT_DATA`, `--sandbox-memory-mb`, default 1024 — enough for about 120 threads), CPU time (timeout + 1 s), size of written files (16 MiB) and open files (256) capped, no core dumps; an environment with only `PATH`, `LANG`, and a throw-away `HOME`, so variables such as API tokens do not reach the target; its own process group, killed when the probe ends. On Linux also a cap on processes (`RLIMIT_NPROC`: the user's current tasks plus 256, since the limit counts all of the user's processes and threads), and the probe adopts processes that detach with `setsid` and ends them before it exits; only when the probe itself is killed on timeout can such a process keep running, and even then it cannot hold up the run, because the probe talks through files, not pipes. |
| `bwrap` | Plus, through bubblewrap: no network, its own PID namespace (every process the target started ends with it, detached or not), the whole file system read-only, and only system directories, the Python installation, the framework, and the analysed project visible — your home directory is not; `/tmp` is an empty in-memory directory of at most 64 MiB holding `HOME`. Needs `bwrap` and unprivileged user namespaces; when they are missing the run stops with an error instead of silently falling back. |

With `limits` the target can still read and write your files and reach the
network. For submissions you did not write, use `bwrap`, or run the whole tool
inside a container or VM.

## Static and runtime rules compared

[`example/architectural_mutants`](../example/architectural_mutants/README.md)
seeds 19 architectural violations into a small layered program and checks
each against a reference that declares the static and the runtime marker for
the same intent wherever both exist. Static rules catch the violations that
need an `import` statement; violations through injected objects, attribute
assignments, computed imports, missing calls, and design patterns are caught
at run time only.
