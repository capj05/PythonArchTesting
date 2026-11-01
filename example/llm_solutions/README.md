# Simulated student solutions (E2/E6)

There are no real submissions (decision D9), so an LLM solves the assignment
instead, several times, and the solutions are checked like submissions.

- `program1/assignment.md`, `program2/assignment.md` — the assignments of the
  two programs of the architectural-mutant evaluation
  (`../architectural_mutants`, `../architectural_mutants_2`): behaviour, the
  public names, and the architecture in prose.
- `program1/skeleton/`, `program2/skeleton/` — the code skeleton of the
  `skeleton` variant: the reference solution's modules, signatures, docstrings
  and `Protocol`s, with every function body replaced by
  `raise NotImplementedError`.
- `generated/<program>/<variant>/<model>-<run>/solution/` — the solutions
  (not versioned; regenerate them as below).
- `evaluate.py` — checks every solution with `--dynamic --sandbox bwrap`
  against the program's reference with its markers, against the reference as
  the model (`architecture_entry` only) and against the same model with
  `policy="layered"`; writes `results.md` and `results.csv`.

## Generating the solutions

Each solution comes from a fresh agent (Claude Haiku, Sonnet, Opus; runs 1
and 2) that may read only the assignment, and in the `skeleton` variant the
skeleton, and must not run code. The prompts, with `<root>` the absolute path
of the repository, `<p>` the program and `<model>-<run>` the run:

`text` variant:

> You are a student solving a programming assignment. Read ONLY this file:
> `<root>/example/llm_solutions/<p>/assignment.md`. Do not open, list or search
> any other file or directory of that repository. Write your complete solution
> as a Python package into the directory
> `<root>/example/llm_solutions/generated/<p>/text/<model>-<run>/solution/`
> (create it; it must contain `__init__.py`). Organise the modules as you see
> fit. Do not execute any code. Reply only with the list of files you wrote.

`skeleton` variant:

> You are a student solving a programming assignment. Read ONLY the assignment
> `<root>/example/llm_solutions/<p>/assignment.md` and the code skeleton your
> teacher gave you in `<root>/example/llm_solutions/<p>/skeleton/` (all files
> there). Do not open, list or search any other file or directory of that
> repository. Copy the skeleton and complete it: write your complete solution
> as a Python package into
> `<root>/example/llm_solutions/generated/<p>/skeleton/<model>-<run>/solution/`
> (create it; keep the skeleton's modules and signatures; you may add
> modules). Do not execute any code. Reply only with the list of files you
> wrote.

For the `text` variant, whose modules are named freely, the matching cannot
pair most entities with the reference. Assisted pairing (F4.4) fixes that:
`proposal.json` next to each solution is the MCP `propose_mapping` output of a
static run against the reference (plus the solution's module list), and an
agent that may read only the proposals and the solutions writes
`mapping.json` (`{"pairs": {"<reference name>": "<target name>"}}`), preferring
module pairs. `evaluate.py` passes a `mapping.json` it finds with `--mapping`.

Then, from the repository root:

```bash
python example/llm_solutions/evaluate.py
```

The results of the 2026-10-31 run (24 solutions) and what they show are in
`results.md` and in `docs/dev_notes/evaluation-f5-2026-10-31.md`. The
solutions differ from run to run, so a new run gives other numbers.
