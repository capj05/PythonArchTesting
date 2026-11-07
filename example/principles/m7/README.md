# M7: natural violations, judge stability, the owner's check of explanations (E2)

The pilot (`../pilot/`) and M6 (`../m6/`) measured the tool on injected
errors; none of their realistic solutions violated a principle on its own.
M7 measures the tool on **natural** violations: solutions that agents
playing first-semester students write, decided by

- **the tool**: the principle's own task (`../<p>/task.toml`), computed
  afresh by `score.py` with the tool as it is then, over the stored
  solutions; the tool's verdicts are never stored, so the data collected now
  stays valid when the tool improves;
- **LLM judges**: Sonnet in two runs (`sonnet-1`, `sonnet-2`: stability) and
  Haiku in one (`haiku-1`), the pilot's prompt J, one judge on one solution;
- **the owner**: the ground truth on a sample (`review.md`), and a rating of
  the 6 VO5 explanations M6 selected for the owner (`owner_vo5.md`), set
  against M6's rater (Opus).

No script here runs an agent; the leader does, with the prompts below.

## Design

Per principle: 3 models (haiku, sonnet, opus) x 2 variants x 2 runs = 12
solutions, each by a fresh agent with prompt N (role `solver-novice`):

- `plain`: the pilot's `assignment.md` unchanged;
- `no-principle`: the same without the principle's section. `stage.py` cuts
  it (`harness.without_principle`): the one level-2 section `## Princip…` /
  `## Principle…` up to the next heading of level 1 or 2, and every other
  sentence naming the principle by the heading's name (the encapsulation
  assignment opens with "Procvičíte princip **Zapouzdření**."). It fails
  loudly when there is not exactly one such section or when the rest still
  mentions a principle (`princip…`).

The packages are named `<ident>_<surname>` as students submit them, from a
fixed list (`harness.NAMES`): one student per (model, variant, run), the
same twelve for every principle (a class solves every task), none of them a
name of the demo or of M6. Stage 1 is `encapsulation` and `io_separation`
(24 solutions, 72 judge runs); any principle with `../<p>/principle.toml`,
`../<p>/task.toml` and a pilot assignment (`../pilot/<p>/assignment.md`) can
be added the same way (`stage.py plan <p>`).

## Layout

```
m7/
  harness.py   the design, the layout, the cut, the tool's verdicts (reuses ../m6/)
  stage.py     staging of solver-novice and judge, collect, plan (the dispatch list)
  forms.py     generates review.md and owner_vo5.md, and reads them
  score.py     writes results.md
  selftest.py  everything end to end on fake agent outputs
  results/                                       versioned: the data
    code/<p>/<ident_surname>/                     the solutions
    meta/<p>/<ident_surname>.json                 model, variant, run, __init__.py
    judgments/<run>/<p>/<ident_surname>.json      one judge run on one solution
    collect.log                                   every collect (append-only)
  review.md      the owner's ground truth (forms.py review, then the owner)
  owner_vo5.md   the owner's VO5 ratings (forms.py vo5, then the owner)
  results.md     score.py
```

The solutions are under `results/code/`, not under a `data/` or
`solutions/` directory: they are what the tool's verdicts are recomputed
from, so they are kept (and copied to the other worktree with the rest).

## Staging

As in the pilot and M6, no agent works in the repository: `stage.py` writes
exactly the inputs of a role into a fresh directory and prints its path
(`<stage>`); the agent reads and writes only there; `stage.py collect
<stage>` validates the output and copies it into the layout. What a stage is
for is kept beside it in `<stage>.stage.json`. Stages go under
`$PAT_STAGE_ROOT` when it is set, else under the pilot's stage root, as
`m7-<role>-<p>-<n>/` (or `--out DIR`).

| Role | `<stage>` holds | The agent writes | `collect` puts it to |
|---|---|---|---|
| `solver-novice <p> --model M --variant V --run N` | `assignment.md` (`plain`: the pilot's; `no-principle`: cut), `submission.txt` (M6's: the package `S/` with `__init__.py`) | `S/` | `results/code/<p>/S/` (files that parse) + `results/meta/<p>/S.json` |
| `judge <p> S --run <model>-<n>` | `assignment.md` (the pilot's, whole), `whole/S.md` (the solution, every file) | `verdicts.json` | `results/judgments/<run>/<p>/S.json` (one valid entry, id `S`) |

`S` is the fixed student of (M, V, N). `collect` replaces an existing
destination only with `--force`. Every `collect` is appended to
`results/collect.log` (one tab-separated line: time, `collect` or `collect
--force`, the stage, the destination, the outcome `placed`, `replaced` or
`refused: <why>`), so a solution refused because it does not parse, and
every replacement, stays on record. The log starts with the change that
added it (2026-11-07): the stage-1 collects before it are not in it.

## Procedure

All commands from the worktree root with its venv; at most 3 agents at
once. Every agent step is: run the row's "Stage it" command, give a fresh
agent of the row's model the prompt below with `<stage>` the printed path,
then `.venv/bin/python example/principles/m7/stage.py collect <stage>`.

1. **Solvers** S1-S24 (prompt N), in any order.
2. **Judges** J1-J72 (prompt J); a judge's row needs its solution collected.
   Do the runs one after another (`sonnet-1` for all, then `sonnet-2`, then
   `haiku-1`); a judge never sees another judge's verdict.
3. **Forms** (2026-11-10): `.venv/bin/python example/principles/m7/forms.py
   review` writes `review.md`, the sample: every solution that **any**
   decider flags (the tool, computed then, or any judge run), every one on
   which they do not all agree (or the tool gives no verdict), and 6 drawn
   with seed 11 from the rest (no one flags, all agree), over all
   principles; `forms.py review --all` puts every solution in the form
   instead. The form is **blind**: per solution only its path, the
   assignment's path and the fields `violates:` / `note:`; neither the
   tool's nor the judges' verdicts, nor error ids, nor why a solution is in
   the sample. Its first line, an HTML comment the owner must not edit, holds
   (base64 JSON) the item set, the tool's verdicts at generation time and
   why each solution is in the sample. `.venv/bin/python
   example/principles/m7/forms.py vo5` writes `owner_vo5.md`: the 6
   explanations listed in `../m6/results-vo3-vo5.md`, each with its code,
   the principle and the text, the M6 rater's rubric, and `location:` /
   `principle:` / `reason:` (0-2) / `note:`, with the same kind of header
   line (the item set); the rater's scores are not shown. Neither overwrites
   an existing form without `--force`.
4. **The owner** fills in the forms (by 2026-11-11 18:00), writing each
   answer on its field's line (`violates: yes`).
5. **Score**: `.venv/bin/python example/principles/m7/score.py` writes
   `results.md`: per principle and variant (`plain`, `no-principle`,
   `both`) the solutions, how many the owner reviewed, how many the tool and
   each judge run flag, the tool's solutions without a verdict, and on how
   many the two Sonnet runs differ; against the owner's ground truth the
   natural violations, and per decider detection on them and FP on the
   clean ones (counts on the enriched sample, with `n no verdict` where the
   tool gave none); VO5 owner x rater per explanation (equal parts of
   three); and every solution with every verdict. A cell the owner has not
   answered reads `pending owner review`, a group without a sampled
   solution `none in the sample` once the owner has answered everything
   (exit 0). A solution not in the form that would enter the sample now
   (the tool changed since the form was generated) is listed under "Needs
   review: not in the form" and not counted. It exits 1, writing nothing, on
   a missing or malformed input: fewer than 12 solutions of a principle that
   has any, a missing meta or judgment, a meta whose (model, variant, run)
   is not its student's fixed slot (`harness.slot`), or a form that does not
   parse. The forms are read strictly: the items must be exactly those of
   the header line, each heading once, each field on exactly one line, a
   value in range, and a non-empty line that is not a field (an answer
   written under an empty `violates:`) is an error naming the item. Also on
   an empty cell.

`.venv/bin/python example/principles/m7/selftest.py` runs all of it on fake
agent outputs in a temporary directory and checks the known counts, the
refusals and that the repository is unchanged.

## Validity threats

What the numbers of `results.md` can and cannot carry (`score.py` points
here from the top of `results.md`):

1. **Sample-based ground truth, enriched.** The owner decides only the
   solutions of `review.md`: every one a decider flags or the deciders
   dispute, plus 6 drawn from the rest. Detection and FP are therefore
   **counts on that sample**, not rates on all solutions; they are reported
   as counts (`detects 1/1`), never as percentages, and the clean rest
   outside the sample is assumed clean, not checked. `forms.py review --all`
   removes this threat at the cost of the owner's time.
2. **Small n.** 12 solutions per principle, 24 in stage 1; one natural
   violation more or less moves any figure a lot. No test of significance
   is meaningful at this size.
3. **One model family.** The solvers (Haiku, Sonnet, Opus) and the judges
   (Sonnet, Haiku) are all Claude; shared blind spots of the family are not
   measured, and the judges may agree with code written in their own style.
4. **LLM novice code is not real novice code.** The prompt asks for a
   first-semester student, but all 24 stage-1 solutions parse and all have
   `__init__.py` (`results/meta/`); real submissions break both more often,
   and their violations may be of other kinds.
5. **Asymmetric norm.** The judges and the owner see the whole assignment,
   principle included; the `no-principle` solvers saw the cut one. A
   `no-principle` solution is judged against a norm its author was not shown
   (which is the point of the variant, but it is not a fair grade).
6. **The cut removes the principle's name, not its structure.** The
   functional specification that stays may still prescribe the structure the
   principle asks for. Especially `io_separation`: `format_summary` returns a
   string and `main()` is the user interface, so even the `no-principle`
   solvers are led to separate logic from I/O, and few natural violations
   are to be expected there.
7. **The owner is the tool's author and the rater.** The ground truth and
   the VO5 ratings come from the person who built the tool; the blind form
   (no verdicts, no reason for the sample) reduces, but does not remove, the
   bias.
8. **Tool version.** The form is generated with the tool as it is then (the
   tool's verdict at generation time decides who enters the sample);
   `score.py` recomputes with the tool as it is when scoring. A changed
   verdict is listed under "The tool's verdict changed", a solution that
   would now enter the sample under "Needs review: not in the form".
9. **Collection refuses non-parsing outputs.** `collect` takes only
   solutions whose Python files all parse; a refused one is re-run, so the
   data holds no broken submission. Refusals are logged in
   `results/collect.log` from 2026-11-07 on, not before.
10. **`missing_required_entity`.** A `failed` verdict with a missing
    required entity *and* another error counts as "violates"; a failure only
    for a missing entity is "no verdict". No `propose_mapping` step is run,
    so a solution that names its entities differently can lose a verdict or
    be judged on the wrong entity.
11. **VO5 ceiling.** The M6 rater (Opus) gave all 6 explanations 2, 2, 2;
    owner x rater agreement can only show whether the owner also gives the
    maximum, not whether the rater discriminates.

## Prompts

`<stage>` is the absolute path `stage.py` printed for this agent; `S` the
row's student.

**N — novice solver** (role `solver-novice`, both variants; the model of
the row):

> You are a student in the first semester of an introductory programming
> course, solving a homework assignment. You write the simplest code that
> works, and you have no time to polish it. Your working directory is
> `<stage>`. Read ONLY `<stage>/assignment.md` and `<stage>/submission.txt`.
> Do not open, list or search anything outside `<stage>`. Write your
> complete solution into the directory `<stage>/S/` (create it) as
> `submission.txt` says. Organise the modules as you see fit. Do not execute
> any code. Reply only with the list of files you wrote.

**J — judge** (role `judge`; the pilot's prompt J verbatim, with the
student's package name as the id, as in M6; Sonnet for `sonnet-*`, Haiku for
`haiku-*`):

> You are a teaching assistant grading ONE programming principle in student
> submissions. Your working directory is `<stage>`. Read ONLY
> `<stage>/assignment.md` (the assignment) and every file in `<stage>/whole/`
> (each the complete code of one student's solution, every file). Do not
> open, list or search anything outside `<stage>`, and do not run code. Judge
> each submission independently and ONLY on the principle «name» as the
> assignment states it: does the code violate it? Any other fault of the
> code does not count. Write a JSON list to `<stage>/verdicts.json`:
> `[{"id": "<id>", "violates": true|false, "reason": "<one sentence>",
> "explanation": "<in Czech: what in the code breaks the principle and why
> it matters; empty when it does not>"}, …]`, one entry per file of
> `<stage>/whole/` (its name without `.md` is the id). Reply only with
> "done".

«name» is the principle's `name` from `describe_principle`
(`.venv/bin/python example/principles/m6/tools.py describe <p>`).

## Dispatch list, stage 1

The output of `.venv/bin/python example/principles/m7/stage.py plan
encapsulation io_separation` (the self-test checks that it is the same).
"Stage it" prints `<stage>`; after the agent, `stage.py collect <stage>`
puts its output to the last column (relative to `example/principles/m7/`).

<!-- plan:start -->
Solvers: 24 runs (prompt N, the model of the row).

| # | Principle | Model | Variant | Run | Student | Stage it | `collect` puts it to |
|---|---|---|---|---|---|---|---|
| S1 | `encapsulation` | haiku | plain | 1 | proa11_prochazka | `.venv/bin/python example/principles/m7/stage.py solver-novice encapsulation --model haiku --variant plain --run 1` | `results/code/encapsulation/proa11_prochazka/` |
| S2 | `encapsulation` | haiku | plain | 2 | kucm12_kucera | `.venv/bin/python example/principles/m7/stage.py solver-novice encapsulation --model haiku --variant plain --run 2` | `results/code/encapsulation/kucm12_kucera/` |
| S3 | `encapsulation` | haiku | no-principle | 1 | cerl13_cerna | `.venv/bin/python example/principles/m7/stage.py solver-novice encapsulation --model haiku --variant no-principle --run 1` | `results/code/encapsulation/cerl13_cerna/` |
| S4 | `encapsulation` | haiku | no-principle | 2 | pokt14_pokorny | `.venv/bin/python example/principles/m7/stage.py solver-novice encapsulation --model haiku --variant no-principle --run 2` | `results/code/encapsulation/pokt14_pokorny/` |
| S5 | `encapsulation` | sonnet | plain | 1 | marp15_marek | `.venv/bin/python example/principles/m7/stage.py solver-novice encapsulation --model sonnet --variant plain --run 1` | `results/code/encapsulation/marp15_marek/` |
| S6 | `encapsulation` | sonnet | plain | 2 | posk16_pospisilova | `.venv/bin/python example/principles/m7/stage.py solver-novice encapsulation --model sonnet --variant plain --run 2` | `results/code/encapsulation/posk16_pospisilova/` |
| S7 | `encapsulation` | sonnet | no-principle | 1 | hajd17_hajek | `.venv/bin/python example/principles/m7/stage.py solver-novice encapsulation --model sonnet --variant no-principle --run 1` | `results/code/encapsulation/hajd17_hajek/` |
| S8 | `encapsulation` | sonnet | no-principle | 2 | jele18_jelinek | `.venv/bin/python example/principles/m7/stage.py solver-novice encapsulation --model sonnet --variant no-principle --run 2` | `results/code/encapsulation/jele18_jelinek/` |
| S9 | `encapsulation` | opus | plain | 1 | ruzv19_ruzicka | `.venv/bin/python example/principles/m7/stage.py solver-novice encapsulation --model opus --variant plain --run 1` | `results/code/encapsulation/ruzv19_ruzicka/` |
| S10 | `encapsulation` | opus | plain | 2 | benz20_benesova | `.venv/bin/python example/principles/m7/stage.py solver-novice encapsulation --model opus --variant plain --run 2` | `results/code/encapsulation/benz20_benesova/` |
| S11 | `encapsulation` | opus | no-principle | 1 | fial21_fiala | `.venv/bin/python example/principles/m7/stage.py solver-novice encapsulation --model opus --variant no-principle --run 1` | `results/code/encapsulation/fial21_fiala/` |
| S12 | `encapsulation` | opus | no-principle | 2 | sedo22_sedlacek | `.venv/bin/python example/principles/m7/stage.py solver-novice encapsulation --model opus --variant no-principle --run 2` | `results/code/encapsulation/sedo22_sedlacek/` |
| S13 | `io_separation` | haiku | plain | 1 | proa11_prochazka | `.venv/bin/python example/principles/m7/stage.py solver-novice io_separation --model haiku --variant plain --run 1` | `results/code/io_separation/proa11_prochazka/` |
| S14 | `io_separation` | haiku | plain | 2 | kucm12_kucera | `.venv/bin/python example/principles/m7/stage.py solver-novice io_separation --model haiku --variant plain --run 2` | `results/code/io_separation/kucm12_kucera/` |
| S15 | `io_separation` | haiku | no-principle | 1 | cerl13_cerna | `.venv/bin/python example/principles/m7/stage.py solver-novice io_separation --model haiku --variant no-principle --run 1` | `results/code/io_separation/cerl13_cerna/` |
| S16 | `io_separation` | haiku | no-principle | 2 | pokt14_pokorny | `.venv/bin/python example/principles/m7/stage.py solver-novice io_separation --model haiku --variant no-principle --run 2` | `results/code/io_separation/pokt14_pokorny/` |
| S17 | `io_separation` | sonnet | plain | 1 | marp15_marek | `.venv/bin/python example/principles/m7/stage.py solver-novice io_separation --model sonnet --variant plain --run 1` | `results/code/io_separation/marp15_marek/` |
| S18 | `io_separation` | sonnet | plain | 2 | posk16_pospisilova | `.venv/bin/python example/principles/m7/stage.py solver-novice io_separation --model sonnet --variant plain --run 2` | `results/code/io_separation/posk16_pospisilova/` |
| S19 | `io_separation` | sonnet | no-principle | 1 | hajd17_hajek | `.venv/bin/python example/principles/m7/stage.py solver-novice io_separation --model sonnet --variant no-principle --run 1` | `results/code/io_separation/hajd17_hajek/` |
| S20 | `io_separation` | sonnet | no-principle | 2 | jele18_jelinek | `.venv/bin/python example/principles/m7/stage.py solver-novice io_separation --model sonnet --variant no-principle --run 2` | `results/code/io_separation/jele18_jelinek/` |
| S21 | `io_separation` | opus | plain | 1 | ruzv19_ruzicka | `.venv/bin/python example/principles/m7/stage.py solver-novice io_separation --model opus --variant plain --run 1` | `results/code/io_separation/ruzv19_ruzicka/` |
| S22 | `io_separation` | opus | plain | 2 | benz20_benesova | `.venv/bin/python example/principles/m7/stage.py solver-novice io_separation --model opus --variant plain --run 2` | `results/code/io_separation/benz20_benesova/` |
| S23 | `io_separation` | opus | no-principle | 1 | fial21_fiala | `.venv/bin/python example/principles/m7/stage.py solver-novice io_separation --model opus --variant no-principle --run 1` | `results/code/io_separation/fial21_fiala/` |
| S24 | `io_separation` | opus | no-principle | 2 | sedo22_sedlacek | `.venv/bin/python example/principles/m7/stage.py solver-novice io_separation --model opus --variant no-principle --run 2` | `results/code/io_separation/sedo22_sedlacek/` |

Judges: 72 runs (prompt J; `sonnet-*` Sonnet, `haiku-*` Haiku), each after the row's solution is collected.

| # | Principle | Judge run | Student | Stage it | `collect` puts it to |
|---|---|---|---|---|---|
| J1 | `encapsulation` | sonnet-1 | proa11_prochazka | `.venv/bin/python example/principles/m7/stage.py judge encapsulation proa11_prochazka --run sonnet-1` | `results/judgments/sonnet-1/encapsulation/proa11_prochazka.json` |
| J2 | `encapsulation` | sonnet-1 | kucm12_kucera | `.venv/bin/python example/principles/m7/stage.py judge encapsulation kucm12_kucera --run sonnet-1` | `results/judgments/sonnet-1/encapsulation/kucm12_kucera.json` |
| J3 | `encapsulation` | sonnet-1 | cerl13_cerna | `.venv/bin/python example/principles/m7/stage.py judge encapsulation cerl13_cerna --run sonnet-1` | `results/judgments/sonnet-1/encapsulation/cerl13_cerna.json` |
| J4 | `encapsulation` | sonnet-1 | pokt14_pokorny | `.venv/bin/python example/principles/m7/stage.py judge encapsulation pokt14_pokorny --run sonnet-1` | `results/judgments/sonnet-1/encapsulation/pokt14_pokorny.json` |
| J5 | `encapsulation` | sonnet-1 | marp15_marek | `.venv/bin/python example/principles/m7/stage.py judge encapsulation marp15_marek --run sonnet-1` | `results/judgments/sonnet-1/encapsulation/marp15_marek.json` |
| J6 | `encapsulation` | sonnet-1 | posk16_pospisilova | `.venv/bin/python example/principles/m7/stage.py judge encapsulation posk16_pospisilova --run sonnet-1` | `results/judgments/sonnet-1/encapsulation/posk16_pospisilova.json` |
| J7 | `encapsulation` | sonnet-1 | hajd17_hajek | `.venv/bin/python example/principles/m7/stage.py judge encapsulation hajd17_hajek --run sonnet-1` | `results/judgments/sonnet-1/encapsulation/hajd17_hajek.json` |
| J8 | `encapsulation` | sonnet-1 | jele18_jelinek | `.venv/bin/python example/principles/m7/stage.py judge encapsulation jele18_jelinek --run sonnet-1` | `results/judgments/sonnet-1/encapsulation/jele18_jelinek.json` |
| J9 | `encapsulation` | sonnet-1 | ruzv19_ruzicka | `.venv/bin/python example/principles/m7/stage.py judge encapsulation ruzv19_ruzicka --run sonnet-1` | `results/judgments/sonnet-1/encapsulation/ruzv19_ruzicka.json` |
| J10 | `encapsulation` | sonnet-1 | benz20_benesova | `.venv/bin/python example/principles/m7/stage.py judge encapsulation benz20_benesova --run sonnet-1` | `results/judgments/sonnet-1/encapsulation/benz20_benesova.json` |
| J11 | `encapsulation` | sonnet-1 | fial21_fiala | `.venv/bin/python example/principles/m7/stage.py judge encapsulation fial21_fiala --run sonnet-1` | `results/judgments/sonnet-1/encapsulation/fial21_fiala.json` |
| J12 | `encapsulation` | sonnet-1 | sedo22_sedlacek | `.venv/bin/python example/principles/m7/stage.py judge encapsulation sedo22_sedlacek --run sonnet-1` | `results/judgments/sonnet-1/encapsulation/sedo22_sedlacek.json` |
| J13 | `io_separation` | sonnet-1 | proa11_prochazka | `.venv/bin/python example/principles/m7/stage.py judge io_separation proa11_prochazka --run sonnet-1` | `results/judgments/sonnet-1/io_separation/proa11_prochazka.json` |
| J14 | `io_separation` | sonnet-1 | kucm12_kucera | `.venv/bin/python example/principles/m7/stage.py judge io_separation kucm12_kucera --run sonnet-1` | `results/judgments/sonnet-1/io_separation/kucm12_kucera.json` |
| J15 | `io_separation` | sonnet-1 | cerl13_cerna | `.venv/bin/python example/principles/m7/stage.py judge io_separation cerl13_cerna --run sonnet-1` | `results/judgments/sonnet-1/io_separation/cerl13_cerna.json` |
| J16 | `io_separation` | sonnet-1 | pokt14_pokorny | `.venv/bin/python example/principles/m7/stage.py judge io_separation pokt14_pokorny --run sonnet-1` | `results/judgments/sonnet-1/io_separation/pokt14_pokorny.json` |
| J17 | `io_separation` | sonnet-1 | marp15_marek | `.venv/bin/python example/principles/m7/stage.py judge io_separation marp15_marek --run sonnet-1` | `results/judgments/sonnet-1/io_separation/marp15_marek.json` |
| J18 | `io_separation` | sonnet-1 | posk16_pospisilova | `.venv/bin/python example/principles/m7/stage.py judge io_separation posk16_pospisilova --run sonnet-1` | `results/judgments/sonnet-1/io_separation/posk16_pospisilova.json` |
| J19 | `io_separation` | sonnet-1 | hajd17_hajek | `.venv/bin/python example/principles/m7/stage.py judge io_separation hajd17_hajek --run sonnet-1` | `results/judgments/sonnet-1/io_separation/hajd17_hajek.json` |
| J20 | `io_separation` | sonnet-1 | jele18_jelinek | `.venv/bin/python example/principles/m7/stage.py judge io_separation jele18_jelinek --run sonnet-1` | `results/judgments/sonnet-1/io_separation/jele18_jelinek.json` |
| J21 | `io_separation` | sonnet-1 | ruzv19_ruzicka | `.venv/bin/python example/principles/m7/stage.py judge io_separation ruzv19_ruzicka --run sonnet-1` | `results/judgments/sonnet-1/io_separation/ruzv19_ruzicka.json` |
| J22 | `io_separation` | sonnet-1 | benz20_benesova | `.venv/bin/python example/principles/m7/stage.py judge io_separation benz20_benesova --run sonnet-1` | `results/judgments/sonnet-1/io_separation/benz20_benesova.json` |
| J23 | `io_separation` | sonnet-1 | fial21_fiala | `.venv/bin/python example/principles/m7/stage.py judge io_separation fial21_fiala --run sonnet-1` | `results/judgments/sonnet-1/io_separation/fial21_fiala.json` |
| J24 | `io_separation` | sonnet-1 | sedo22_sedlacek | `.venv/bin/python example/principles/m7/stage.py judge io_separation sedo22_sedlacek --run sonnet-1` | `results/judgments/sonnet-1/io_separation/sedo22_sedlacek.json` |
| J25 | `encapsulation` | sonnet-2 | proa11_prochazka | `.venv/bin/python example/principles/m7/stage.py judge encapsulation proa11_prochazka --run sonnet-2` | `results/judgments/sonnet-2/encapsulation/proa11_prochazka.json` |
| J26 | `encapsulation` | sonnet-2 | kucm12_kucera | `.venv/bin/python example/principles/m7/stage.py judge encapsulation kucm12_kucera --run sonnet-2` | `results/judgments/sonnet-2/encapsulation/kucm12_kucera.json` |
| J27 | `encapsulation` | sonnet-2 | cerl13_cerna | `.venv/bin/python example/principles/m7/stage.py judge encapsulation cerl13_cerna --run sonnet-2` | `results/judgments/sonnet-2/encapsulation/cerl13_cerna.json` |
| J28 | `encapsulation` | sonnet-2 | pokt14_pokorny | `.venv/bin/python example/principles/m7/stage.py judge encapsulation pokt14_pokorny --run sonnet-2` | `results/judgments/sonnet-2/encapsulation/pokt14_pokorny.json` |
| J29 | `encapsulation` | sonnet-2 | marp15_marek | `.venv/bin/python example/principles/m7/stage.py judge encapsulation marp15_marek --run sonnet-2` | `results/judgments/sonnet-2/encapsulation/marp15_marek.json` |
| J30 | `encapsulation` | sonnet-2 | posk16_pospisilova | `.venv/bin/python example/principles/m7/stage.py judge encapsulation posk16_pospisilova --run sonnet-2` | `results/judgments/sonnet-2/encapsulation/posk16_pospisilova.json` |
| J31 | `encapsulation` | sonnet-2 | hajd17_hajek | `.venv/bin/python example/principles/m7/stage.py judge encapsulation hajd17_hajek --run sonnet-2` | `results/judgments/sonnet-2/encapsulation/hajd17_hajek.json` |
| J32 | `encapsulation` | sonnet-2 | jele18_jelinek | `.venv/bin/python example/principles/m7/stage.py judge encapsulation jele18_jelinek --run sonnet-2` | `results/judgments/sonnet-2/encapsulation/jele18_jelinek.json` |
| J33 | `encapsulation` | sonnet-2 | ruzv19_ruzicka | `.venv/bin/python example/principles/m7/stage.py judge encapsulation ruzv19_ruzicka --run sonnet-2` | `results/judgments/sonnet-2/encapsulation/ruzv19_ruzicka.json` |
| J34 | `encapsulation` | sonnet-2 | benz20_benesova | `.venv/bin/python example/principles/m7/stage.py judge encapsulation benz20_benesova --run sonnet-2` | `results/judgments/sonnet-2/encapsulation/benz20_benesova.json` |
| J35 | `encapsulation` | sonnet-2 | fial21_fiala | `.venv/bin/python example/principles/m7/stage.py judge encapsulation fial21_fiala --run sonnet-2` | `results/judgments/sonnet-2/encapsulation/fial21_fiala.json` |
| J36 | `encapsulation` | sonnet-2 | sedo22_sedlacek | `.venv/bin/python example/principles/m7/stage.py judge encapsulation sedo22_sedlacek --run sonnet-2` | `results/judgments/sonnet-2/encapsulation/sedo22_sedlacek.json` |
| J37 | `io_separation` | sonnet-2 | proa11_prochazka | `.venv/bin/python example/principles/m7/stage.py judge io_separation proa11_prochazka --run sonnet-2` | `results/judgments/sonnet-2/io_separation/proa11_prochazka.json` |
| J38 | `io_separation` | sonnet-2 | kucm12_kucera | `.venv/bin/python example/principles/m7/stage.py judge io_separation kucm12_kucera --run sonnet-2` | `results/judgments/sonnet-2/io_separation/kucm12_kucera.json` |
| J39 | `io_separation` | sonnet-2 | cerl13_cerna | `.venv/bin/python example/principles/m7/stage.py judge io_separation cerl13_cerna --run sonnet-2` | `results/judgments/sonnet-2/io_separation/cerl13_cerna.json` |
| J40 | `io_separation` | sonnet-2 | pokt14_pokorny | `.venv/bin/python example/principles/m7/stage.py judge io_separation pokt14_pokorny --run sonnet-2` | `results/judgments/sonnet-2/io_separation/pokt14_pokorny.json` |
| J41 | `io_separation` | sonnet-2 | marp15_marek | `.venv/bin/python example/principles/m7/stage.py judge io_separation marp15_marek --run sonnet-2` | `results/judgments/sonnet-2/io_separation/marp15_marek.json` |
| J42 | `io_separation` | sonnet-2 | posk16_pospisilova | `.venv/bin/python example/principles/m7/stage.py judge io_separation posk16_pospisilova --run sonnet-2` | `results/judgments/sonnet-2/io_separation/posk16_pospisilova.json` |
| J43 | `io_separation` | sonnet-2 | hajd17_hajek | `.venv/bin/python example/principles/m7/stage.py judge io_separation hajd17_hajek --run sonnet-2` | `results/judgments/sonnet-2/io_separation/hajd17_hajek.json` |
| J44 | `io_separation` | sonnet-2 | jele18_jelinek | `.venv/bin/python example/principles/m7/stage.py judge io_separation jele18_jelinek --run sonnet-2` | `results/judgments/sonnet-2/io_separation/jele18_jelinek.json` |
| J45 | `io_separation` | sonnet-2 | ruzv19_ruzicka | `.venv/bin/python example/principles/m7/stage.py judge io_separation ruzv19_ruzicka --run sonnet-2` | `results/judgments/sonnet-2/io_separation/ruzv19_ruzicka.json` |
| J46 | `io_separation` | sonnet-2 | benz20_benesova | `.venv/bin/python example/principles/m7/stage.py judge io_separation benz20_benesova --run sonnet-2` | `results/judgments/sonnet-2/io_separation/benz20_benesova.json` |
| J47 | `io_separation` | sonnet-2 | fial21_fiala | `.venv/bin/python example/principles/m7/stage.py judge io_separation fial21_fiala --run sonnet-2` | `results/judgments/sonnet-2/io_separation/fial21_fiala.json` |
| J48 | `io_separation` | sonnet-2 | sedo22_sedlacek | `.venv/bin/python example/principles/m7/stage.py judge io_separation sedo22_sedlacek --run sonnet-2` | `results/judgments/sonnet-2/io_separation/sedo22_sedlacek.json` |
| J49 | `encapsulation` | haiku-1 | proa11_prochazka | `.venv/bin/python example/principles/m7/stage.py judge encapsulation proa11_prochazka --run haiku-1` | `results/judgments/haiku-1/encapsulation/proa11_prochazka.json` |
| J50 | `encapsulation` | haiku-1 | kucm12_kucera | `.venv/bin/python example/principles/m7/stage.py judge encapsulation kucm12_kucera --run haiku-1` | `results/judgments/haiku-1/encapsulation/kucm12_kucera.json` |
| J51 | `encapsulation` | haiku-1 | cerl13_cerna | `.venv/bin/python example/principles/m7/stage.py judge encapsulation cerl13_cerna --run haiku-1` | `results/judgments/haiku-1/encapsulation/cerl13_cerna.json` |
| J52 | `encapsulation` | haiku-1 | pokt14_pokorny | `.venv/bin/python example/principles/m7/stage.py judge encapsulation pokt14_pokorny --run haiku-1` | `results/judgments/haiku-1/encapsulation/pokt14_pokorny.json` |
| J53 | `encapsulation` | haiku-1 | marp15_marek | `.venv/bin/python example/principles/m7/stage.py judge encapsulation marp15_marek --run haiku-1` | `results/judgments/haiku-1/encapsulation/marp15_marek.json` |
| J54 | `encapsulation` | haiku-1 | posk16_pospisilova | `.venv/bin/python example/principles/m7/stage.py judge encapsulation posk16_pospisilova --run haiku-1` | `results/judgments/haiku-1/encapsulation/posk16_pospisilova.json` |
| J55 | `encapsulation` | haiku-1 | hajd17_hajek | `.venv/bin/python example/principles/m7/stage.py judge encapsulation hajd17_hajek --run haiku-1` | `results/judgments/haiku-1/encapsulation/hajd17_hajek.json` |
| J56 | `encapsulation` | haiku-1 | jele18_jelinek | `.venv/bin/python example/principles/m7/stage.py judge encapsulation jele18_jelinek --run haiku-1` | `results/judgments/haiku-1/encapsulation/jele18_jelinek.json` |
| J57 | `encapsulation` | haiku-1 | ruzv19_ruzicka | `.venv/bin/python example/principles/m7/stage.py judge encapsulation ruzv19_ruzicka --run haiku-1` | `results/judgments/haiku-1/encapsulation/ruzv19_ruzicka.json` |
| J58 | `encapsulation` | haiku-1 | benz20_benesova | `.venv/bin/python example/principles/m7/stage.py judge encapsulation benz20_benesova --run haiku-1` | `results/judgments/haiku-1/encapsulation/benz20_benesova.json` |
| J59 | `encapsulation` | haiku-1 | fial21_fiala | `.venv/bin/python example/principles/m7/stage.py judge encapsulation fial21_fiala --run haiku-1` | `results/judgments/haiku-1/encapsulation/fial21_fiala.json` |
| J60 | `encapsulation` | haiku-1 | sedo22_sedlacek | `.venv/bin/python example/principles/m7/stage.py judge encapsulation sedo22_sedlacek --run haiku-1` | `results/judgments/haiku-1/encapsulation/sedo22_sedlacek.json` |
| J61 | `io_separation` | haiku-1 | proa11_prochazka | `.venv/bin/python example/principles/m7/stage.py judge io_separation proa11_prochazka --run haiku-1` | `results/judgments/haiku-1/io_separation/proa11_prochazka.json` |
| J62 | `io_separation` | haiku-1 | kucm12_kucera | `.venv/bin/python example/principles/m7/stage.py judge io_separation kucm12_kucera --run haiku-1` | `results/judgments/haiku-1/io_separation/kucm12_kucera.json` |
| J63 | `io_separation` | haiku-1 | cerl13_cerna | `.venv/bin/python example/principles/m7/stage.py judge io_separation cerl13_cerna --run haiku-1` | `results/judgments/haiku-1/io_separation/cerl13_cerna.json` |
| J64 | `io_separation` | haiku-1 | pokt14_pokorny | `.venv/bin/python example/principles/m7/stage.py judge io_separation pokt14_pokorny --run haiku-1` | `results/judgments/haiku-1/io_separation/pokt14_pokorny.json` |
| J65 | `io_separation` | haiku-1 | marp15_marek | `.venv/bin/python example/principles/m7/stage.py judge io_separation marp15_marek --run haiku-1` | `results/judgments/haiku-1/io_separation/marp15_marek.json` |
| J66 | `io_separation` | haiku-1 | posk16_pospisilova | `.venv/bin/python example/principles/m7/stage.py judge io_separation posk16_pospisilova --run haiku-1` | `results/judgments/haiku-1/io_separation/posk16_pospisilova.json` |
| J67 | `io_separation` | haiku-1 | hajd17_hajek | `.venv/bin/python example/principles/m7/stage.py judge io_separation hajd17_hajek --run haiku-1` | `results/judgments/haiku-1/io_separation/hajd17_hajek.json` |
| J68 | `io_separation` | haiku-1 | jele18_jelinek | `.venv/bin/python example/principles/m7/stage.py judge io_separation jele18_jelinek --run haiku-1` | `results/judgments/haiku-1/io_separation/jele18_jelinek.json` |
| J69 | `io_separation` | haiku-1 | ruzv19_ruzicka | `.venv/bin/python example/principles/m7/stage.py judge io_separation ruzv19_ruzicka --run haiku-1` | `results/judgments/haiku-1/io_separation/ruzv19_ruzicka.json` |
| J70 | `io_separation` | haiku-1 | benz20_benesova | `.venv/bin/python example/principles/m7/stage.py judge io_separation benz20_benesova --run haiku-1` | `results/judgments/haiku-1/io_separation/benz20_benesova.json` |
| J71 | `io_separation` | haiku-1 | fial21_fiala | `.venv/bin/python example/principles/m7/stage.py judge io_separation fial21_fiala --run haiku-1` | `results/judgments/haiku-1/io_separation/fial21_fiala.json` |
| J72 | `io_separation` | haiku-1 | sedo22_sedlacek | `.venv/bin/python example/principles/m7/stage.py judge io_separation sedo22_sedlacek --run haiku-1` | `results/judgments/haiku-1/io_separation/sedo22_sedlacek.json` |
<!-- plan:end -->
