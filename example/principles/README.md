# Principle catalogue (pilot)

Each directory is one **principle** of an introductory Python course, checked
the way a teacher would grade one task: did the student apply *this*
principle? Everything else about the code is deliberately ignored.

| Directory | Principle | Level |
|---|---|---|
| `io_separation/` | Logic apart from input and output (functions return, `main` talks to the user) | basic |
| `encapsulation/` | Encapsulation (an object's state changes only through its own methods) | basic |
| `polymorphism/` | Inheritance and polymorphism instead of branching on the type (variants of an abstract base; clients call its methods, no test of an object's class) | basic |
| `strategy/` | Interchangeable behaviour passed in from outside (the code doing a job gets the object for one part of it in its constructor, calls it and never builds it) | basic |

## Layout of one principle

```
<principle>/
  principle.toml     points to the catalogue entry; maps its items to variants
  task.toml          the task: the entry's roles bound to reference/, the cases
  reference/         model solution of a small task, without markers
  assignments/
    ok_*/            neutral changes: unrelated to the principle, must PASS
    err_*/           one typical error each: must FAIL (or is a documented gap)
```

The catalogue entries ship with the tool, in
`src/pythonarchtesting/principles/catalog/<id>.toml` (an MCP client reads them
with `list_principles` and `describe_principle`, see `docs/mcp.md`).
`<principle>/principle.toml` here names its entry (`id`) and maps each error
and neutral change to its variant under `assignments/` (`[examples]`).
`<principle>/task.toml` is the task ([docs/tasks.md](../../docs/tasks.md)): it
binds each of the entry's generic roles to what plays it in `reference/`
(`[roles]`) and gives every bound function its cases (`[cases]`); the tool
compiles the entry's checks from it, so `reference/` carries no markers. An
entry has:

- `summary` and `why` describe the principle for the assignment text;
- `[[checks]]` says which marker covers which role and what the cases must
  exercise;
- `[[errors]]` lists the typical errors. Each has either `detected_by` (the
  marker that must fail), with the `signature` of the failure's first fact, or
  `gap` (a known miss). Each also has the explanation: `what` with placeholders
  filled from the report, plus `why` and `fix`;
- `[[neutral]]` lists the changes that must not count as errors;
- `[[gaps]]` lists what the tool cannot check yet, and why.

Keys and texts are English; the teacher's AI client words them for students in
any language.

## Verify

```bash
python example/principles/verify.py            # every principle
python example/principles/verify.py encapsulation
```

`verify.py` runs the tool once per principle with the principle directory, the
task, as `--source` (`--dynamic --sandbox bwrap`),
checks every variant against its entry (a detected error must also fail with
its declared signature, compared on the keys it declares, and be the error
`choose_error` picks), and composes the explanation
of each detected error from the entry and the report facts, without any LLM
(`explain.py`, shared with the pilot's `pilot/run_tool.py`; see
`pilot/README.md` for the pilot evaluation on agents' solutions). It writes `results.md` and exits 1 when a variant does not behave as
promised. It needs Python 3.11+ for `tomllib`; the tool itself supports 3.10.

Neither the targets nor `reference/` carry `__archtest__` metadata; what is
checked is `task.toml`. `prepare_task` (MCP) checks a task before a class is
graded.
