# Principle catalogue (pilot)

Each directory is one **principle** of an introductory Python course, checked
the way a teacher would grade one task: did the student apply *this*
principle? Everything else about the code is deliberately ignored.

| Directory | Principle | Level |
|---|---|---|
| `io_separation/` | Logic apart from input and output (functions return, `main` talks to the user) | basic |
| `encapsulation/` | Encapsulation (an object's state changes only through its own methods) | basic |

## Layout of one principle

```
<principle>/
  principle.toml     catalogue entry: checks, typical errors, neutral changes, gaps
  reference/         model solution of a small task, with the markers
  assignments/
    ok_*/            neutral changes: unrelated to the principle, must PASS
    err_*/           one typical error each: must FAIL (or is a documented gap)
```

`principle.toml` is the catalogue entry:

- `summary` and `why` describe the principle for the assignment text;
- `[[checks]]` says which marker covers which role and what the cases must
  exercise;
- `[[errors]]` lists the typical errors. Each has an example variant and either
  `detected_by` (the marker that must fail) or `gap` (a known miss). Each also
  has the student explanation: `what` with placeholders filled from the
  report, plus `why` and `fix`;
- `[[neutral]]` lists the changes that must not count as errors;
- `[[gaps]]` lists what the tool cannot check yet, and why.

The keys are English. The texts are Czech, because they are written for the
students of the course.

## Verify

```bash
python example/principles/verify.py            # every principle
python example/principles/verify.py encapsulation
```

`verify.py` runs the tool once per principle (`--dynamic --sandbox bwrap`),
checks every variant against its entry, and composes the student explanation
of each detected error from the entry and the report facts, without any LLM
(`explain.py`, shared with the pilot's `pilot/run_tool.py`; see
`pilot/README.md` for the pilot evaluation on agents' solutions). It writes `results.md` and exits 1 when a variant does not behave as
promised. It needs Python 3.11+ for `tomllib`; the tool itself supports 3.10.

Targets carry no `__archtest__` metadata; the markers live only in
`reference/`.
