# LLM as judge versus the tool (E3)

Does an LLM, asked directly, judge the architecture of a change as well as the
tool? The same 91 variants as the architectural-mutant evaluation (the
hand-written and the held-out mutants and equivalent rewrites of both
programs) are judged blind by LLM agents and compared with the tool's verdicts.

- `prepare.py` writes, per program, `context.md` (the assignment with its
  graded architecture requirements and the correct solution) and
  `variants/vNNN.diff` (each variant as a diff against the solution, under a
  neutral id, shuffled), `batches.json` and `key.json` (which id is which
  variant; never shown to a judge).
- `judgments/<model>-<run>/<program>-b<N>.json` — the verdicts: one agent per
  batch of up to 10 diffs, which may read only `context.md` and its diffs.
  Runs: Claude Sonnet twice (stability), Claude Haiku once.
- `score.py` writes `results.md`: detection on mutants and false positives on
  equivalents per judge run and per tool configuration, agreement between
  runs, and the variants on which the judges' majority and the tool differ.

The judges' inputs (`program1/`, `program2/`: `context.md`, the diffs, the
whole submissions, the batches) are not checked in: the whole submissions
contain the code of the generated E2 solutions, which stay out of the
repository. `python example/llm_judge/prepare.py` and
`prepare.py --whole --batch-size 8` rebuild them byte for byte (fixed seed;
the whole submissions need the local `llm_solutions/generated/`). The keys,
the verdicts and the results are checked in.

The judge prompt (batch `vAAA … vBBB` of `<program>`, run `<run>`):

> You are a teaching assistant grading the ARCHITECTURE of student code
> changes. Base dir: `<root>/example/llm_judge/<program>`. Read ONLY:
> `<base>/context.md` (the assignment with its graded architecture
> requirements 1–8, and the correct solution), and the diff files
> `<base>/variants/vAAA.diff … vBBB.diff` (each a student's change to the
> correct solution). Do not open any other file, list directories, or run
> code. Judge each diff independently: does the changed code violate any
> graded architecture requirement? Restructuring that keeps the architecture
> (helpers, helper modules used the same way, renamed locals, other idioms) is
> NOT a violation. Write a JSON list to
> `<base>/../judgments/<run>/<program>-b<N>.json`: `[{"id": "vAAA", "violates":
> true|false, "requirements": [...], "reason": "<one sentence>"}, …]` — one
> entry per diff. Reply only with "done".

## Whole submissions

`prepare.py --whole` writes the same 91 variants as the complete code of the
submission (every file, `<program>/whole/wNNN.md`) plus the 24 independently
written solutions of E2, shuffled under new ids (`key-whole.json`,
`batches-whole.json`); `judgments-whole/<run>/` holds the verdicts (Sonnet and
Haiku, one run each, one agent per two or three batches of 8) and
`score.py --whole` writes `results-whole.md`, which adds how many E2 solutions
each decider flags (none has a known violation) and lists them. The prompt is
the one above, with "submission files … each the COMPLETE code of one
student's solution (every file), not a diff" and "a different structure that
keeps the architecture (other module or function names, …) is NOT a
violation".

Without the diff the judges did not get worse: Sonnet caught 59 of 61
mutants, Haiku 56, neither flagged an equivalent, and neither flagged any E2
solution, where the tool flags 10 of 24 (its known false positives on freely
structured code). See `docs/dev_notes/evaluation-f5-2026-10-31.md` for the
limits.

## The diff setting

The judge sees a diff against the correct solution: it is told exactly what
changed. The tool sees a whole submission and must first pair it with the
reference. The comparison is therefore favourable to the judge; see
`docs/dev_notes/evaluation-f5-2026-10-31.md`.
