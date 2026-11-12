# Pilot evaluation of the principle catalogue

Does the tool tell, on code written by agents, whether a student applied the
principle? And does it do so better than an LLM asked directly? For each
principle of the catalogue (`io_separation`, `encapsulation`), agents write
solutions of a small task, other agents inject one typical error of the
principle or one defect unrelated to it into clean solutions, and every
submission is judged blind by the tool and by LLM judges.

Scope per principle: 3 models (Haiku, Sonnet, Opus) × 2 runs × 2 variants
(`text`, `skeleton`) = 12 solutions; 3 errors × 3 carriers = 9 injected
errors; 4 neutral defects × 3 carriers = 12 injected defects; 33 submissions,
each judged by the tool and by Sonnet and Haiku. At most 3 agents run at once.

## Layout

```
pilot/
  make_skeleton.py  prepare.py  run_tool.py  score.py  stage.py  selftest.py
  <p>/
    skeleton/        code skeleton from ../<p>/reference (make_skeleton.py)
    assignment.md    the assignment, written by an agent, reviewed by the leader
    solutions/<variant>/<model>-<run>/solution/            agents' solutions
    injected/err/<id>-<carrier_>/solution/ + meta.json     injected errors
    injected/neutral/<id>-<carrier_>/solution/ + meta.json injected defects
    whole/wNNN.md    each submission's complete code, under a neutral id
    key.json         wNNN -> what it is, and the sha256 of whole/wNNN.md
                     (never shown to a judge)
    batches.json     the ids in batches of at most 4, one per carrier family
    tool.json        the tool's verdict, explanations and hash per submission
  judgments/<run>/<p>-b<N>.json   the judges' verdicts
  results.md  results.csv
```

`<carrier>` is the carrier solution as `<variant>/<model>-<run>`;
`<carrier_>` is the same with `/` replaced by `_` (a directory name; an
injected variant's directory must be exactly `<id>-<carrier_>`).
`meta.json` of an injected variant is
`{"kind": "err"|"neutral", "id": "<id>", "carrier": "<carrier>", "injector": "<model>"}`.
An error `id` is the catalogue's `[[errors]] id`; a defect `id` is a
`[[neutral]] id` of the catalogue or `input_handling`. A carrier family is a
carrier solution and every variant injected into it; a solution nothing was
injected into is a family of its own.

Versioned: the scripts, this README, `<p>/skeleton/`, `<p>/assignment.md`,
`<p>/key.json`, `<p>/batches.json`, `<p>/tool.json`, `judgments/`,
`results.md`, `results.csv`. Not versioned (`.gitignore`): `<p>/solutions/`,
`<p>/injected/`, `<p>/whole/`; they hold agents' code, as E2's `generated/`.

## Staging: what each agent can see

A prompt that says "read only X" does not stop an agent from reading the
repository. So no agent works in the repository: `stage.py` copies exactly
the inputs its role may see into a fresh directory, the agent reads and
writes only there, and `stage.py collect` validates the output and copies it
into the pilot.

```
python example/principles/pilot/stage.py <role> <p> [--run <model>-<run>]
    [--carrier <variant>/<model>-<run>] [--id <id>] [--batch N] [--out DIR]
python example/principles/pilot/stage.py collect <stage> [--injector <model>] [--force]
```

| Role | `<stage>` holds | The agent writes | `collect` puts it to |
|---|---|---|---|
| `author` | `principle.txt` (name, summary, why), `skeleton/` | `assignment.md` | `<p>/assignment.md` |
| `solver-text` (`--run`) | `assignment.md` | `solution/` | `<p>/solutions/text/<run>/solution/` |
| `solver-skeleton` (`--run`) | `assignment.md`, `skeleton/` | `solution/` | `<p>/solutions/skeleton/<run>/solution/` |
| `injector-err` (`--carrier`, `--id`) | `solution/` (the carrier), `error.txt` (title, why) | `solution/`, changed | `<p>/injected/err/<id>-<carrier_>/` + `meta.json` |
| `injector-neutral` (`--carrier`, `--id`) | `solution/` (the carrier), `defect.txt` (the defect, the principle's name and summary) | `solution/`, changed | `<p>/injected/neutral/<id>-<carrier_>/` + `meta.json` |
| `judge` (`--batch`, `--run`) | `assignment.md`, `whole/` of one batch | `verdicts.json` | `judgments/<run>/<p>-b<N>.json` |

The stage directory is
`/tmp/claude-1000/-home-jirka-git-PythonArchTesting/8173ba2d-10ce-4d65-89ca-58dad548b14d/scratchpad/stage/<role>-<p>-<n>/`
(or `--out`); what it is for is kept beside it in `<stage>.stage.json`,
outside the agent's reach. `collect` checks that a solution is a package
whose every file parses, that an injected one differs from its carrier, and
that a judge's file has one valid entry per id of its batch; it writes an
injector's `meta.json` itself (`--injector`), and replaces an existing
destination only with `--force`.

## Procedure

All commands run from the repository root with the worktree's venv
(Python 3.11+; the tool runs `--dynamic --sandbox bwrap`). Every agent step
is: `stage.py <role> ...`, the agent with its prompt below and `<stage>` the
printed path, then `stage.py collect <stage>`.

1. **Skeleton.** `python example/principles/pilot/make_skeleton.py io_separation encapsulation`
   (deterministic; the markers, the tool's imports, the module and package
   docstrings and every function body go; function and class docstrings
   stay; it fails when the skeleton still names how solutions are checked).
2. **Assignment.** One agent (Sonnet) per principle writes `assignment.md`
   (role `author`, prompt A). The leader reviews it before any solution is
   generated.
3. **Solutions.** One fresh agent per solution (roles `solver-text`,
   `solver-skeleton`; prompts S-text, S-skeleton).
4. **Carriers.** Fixed by rule, independent of any decider: `skeleton/haiku-1`,
   `skeleton/sonnet-1`, `skeleton/opus-1`. Neither the tool's verdict nor a
   manual read chooses them: picking carriers the tool passes would bias the
   comparison towards the tool. `score.py` reports each decider's verdict on
   every carrier instead, and its rates over the carriers that decider
   considers clean.
5. **Injection.** One fresh agent per injected variant (roles `injector-err`,
   `injector-neutral`; prompts E and N), other than the one that wrote the
   carrier. The leader picks 3 errors and 4 defects per principle.
6. **Blind inputs.** `python example/principles/pilot/prepare.py` (fixed seed
   7; ids shuffled across kinds; batches of at most 4, never two submissions
   of one carrier family in a batch). Do not rerun it after the judges start:
   new inputs give new ids, and `score.py` refuses judgments whose inputs
   changed (the `sha256` in `key.json`).
7. **Tool.** `python example/principles/pilot/run_tool.py` writes
   `<p>/tool.json`: `FAIL` / `PASS` / `UNMATCHED` (only
   `required_target_missing` failed: no verdict, as in E1–E5), the failed
   rules, the rules that could not run the code (`not_run`), the student
   explanation of each failure, composed from the catalogue by the same code
   as `verify.py` (`../explain.py`), and the `sha256` of the code it checked.
   The source is the principle's task (`../<p>/`: `task.toml` beside the
   unannotated reference, `docs/tasks.md`). The recorded `tool.json` was
   rerun on 2026-11-11 with the tool that checks reads of private attributes
   (`forbid_private_access`, ENC001): the 3 injected `read_private` errors
   now fail and one `mutate_container` error fails on ENC001 too; every other
   submission keeps its verdict and its failed rules.
8. **Judges.** One agent per batch (role `judge`, prompt J); runs `sonnet-1`,
   `haiku-1`.
9. **Score.** `python example/principles/pilot/score.py` writes `results.md`
   and `results.csv` (one row per submission, with `tool_not_run`). Per
   principle, columns are the tool and each judge run; rows are injected
   errors flagged, defects flagged (FP), clean solutions flagged, unmatched,
   not run (`nespuštěno`), and detection and FP again over the variants whose
   carrier that decider considers clean (the tool `PASS`, a judge
   `violates: false`), denominators shown. Submissions the tool did not run
   are left out of the tool's rates. Then each decider's verdict on every
   carrier, and the solutions anyone flagged, to be checked by hand for
   natural violations. It exits 1 when `tool.json` or a judge verdict is
   missing, a judge file is malformed (not a list, an entry without a key, an
   id twice in one run), or a hash differs between `key.json`, `tool.json`
   and `whole/`.

`python example/principles/pilot/selftest.py` checks the harness on fake
data built from the catalogue's own variants in a temporary directory: the
tool must give each the verdict and explanation `verify.py` gives, a renamed
function must come out `UNMATCHED` and code that raises on import `not_run`,
the batches must keep the family rule, one judge stage and its `collect` must
hold exactly the batch and land where `score.py` reads it, the tool's counts
must be the known ones (errors N/N, defects 0/N, clean 0/2), `score.py` must
refuse a missing verdict, a malformed judge file and a stale hash, and the
repository stays unchanged.

## Prompts

`<stage>` is the absolute path `stage.py` printed for this agent. Text in
`«…»` is pasted verbatim from the catalogue entry
(`src/pythonarchtesting/principles/catalog/<p>.toml`); the agent does not
read that file. The recorded run used the Czech texts of commit `c1152c6`: the
entries then kept in `../<p>/principle.toml`, and Czech labels in the files
`stage.py` writes (`principle.txt`, `error.txt`, `defect.txt`), which are
English now.

**A — assignment author** (role `author`; the stage holds the principle's
name, summary and why, and the skeleton):

> You are a teacher of an introductory Python course writing an assignment
> for your students. The assignment practises one principle: «name».
> Your working directory is `<stage>`. Read ONLY the files in it:
> `<stage>/principle.txt` (the principle and why it matters) and the code
> skeleton the students will get, all files in `<stage>/skeleton/`. Do not
> open, list or search anything outside `<stage>`. Write the assignment in
> Czech into `<stage>/assignment.md`: what the program does (its behaviour,
> inputs, outputs and error cases, with an example run), the modules, classes
> and functions with their signatures exactly as in the skeleton, and the
> principle by name with one paragraph on what it means in this task. Do not
> say how solutions will be checked, do not list typical mistakes, and do not
> write any of the solution's code. Do not execute any code. Reply only with
> "done".

**S-text — solver, `text` variant** (role `solver-text`; the stage holds
`assignment.md`):

> You are a student solving a programming assignment. Your working directory
> is `<stage>`. Read ONLY `<stage>/assignment.md`. Do not open, list or search
> anything outside `<stage>`. Write your complete solution as a Python package
> into the directory `<stage>/solution/` (create it; it must contain
> `__init__.py`). Organise the modules as you see fit. Do not execute any
> code. Reply only with the list of files you wrote.

**S-skeleton — solver, `skeleton` variant** (role `solver-skeleton`; the
stage holds `assignment.md` and the skeleton):

> You are a student solving a programming assignment. Your working directory
> is `<stage>`. Read ONLY the assignment `<stage>/assignment.md` and the code
> skeleton your teacher gave you in `<stage>/skeleton/` (all files there). Do
> not open, list or search anything outside `<stage>`. Copy the skeleton and
> complete it: write your complete solution as a Python package into
> `<stage>/solution/` (create it; keep the skeleton's modules and signatures;
> you may add modules). Do not execute any code. Reply only with the list of
> files you wrote.

**E — error injector** (role `injector-err`; the stage holds the carrier as
`solution/` and the `title` and `why` of one `[[errors]]` entry):

> You are preparing test data for a study of how beginners' mistakes are
> detected. Your working directory is `<stage>`. Read ONLY the files in it:
> the student's solution in `<stage>/solution/` and the mistake in
> `<stage>/error.txt`. Do not open, list or search anything outside
> `<stage>`. Change the files in `<stage>/solution/` in place so that the
> solution makes exactly the mistake that `error.txt` describes. Change as
> little as possible: the program must still run and do everything else as
> before, and the change must look like the student's own code (no comment,
> name or docstring may point at it). Do not execute any code. Reply only
> with the files you changed and one sentence on the change.

**N — neutral defect injector** (role `injector-neutral`; the stage holds the
carrier as `solution/` and the defect with the principle to leave alone):

> You are preparing test data for a study of how beginners' mistakes are
> detected. Your working directory is `<stage>`. Read ONLY the files in it:
> the student's solution in `<stage>/solution/` and `<stage>/defect.txt`.
> Do not open, list or search anything outside `<stage>`. Change the files in
> `<stage>/solution/` in place so that the solution has exactly the one
> defect `defect.txt` describes. The change must not touch anything that
> concerns the principle `defect.txt` names: code that follows it must still
> follow it, in the same way. Change as little as possible, and make the
> change look like the student's own code (no comment, name or docstring may
> point at it). Do not execute any code. Reply only with the files you
> changed and one sentence on the change.

The defects (`--id`; the leader picks 4 per principle): `io_separation`:
`different_ui`, `extra_pure_helper`, `wrong_formula`, `style_noise`;
`encapsulation`: `property`, `extra_method`, `wrong_math`, `style_noise`;
both: `input_handling` («chyba ošetření vstupu: neplatný nebo prázdný vstup
se neodmítne nebo neošetří (chybí kontrola nebo zachycení výjimky)», kept in
`prepare.py` as `EXTRA_NEUTRAL`). `stage.py` writes the defect's `title` into
`defect.txt`.

**J — judge** (role `judge`; the stage holds `assignment.md` and the
`whole/` files of one batch):

> You are a teaching assistant grading ONE programming principle in student
> submissions. Your working directory is `<stage>`. Read ONLY
> `<stage>/assignment.md` (the assignment) and every file in `<stage>/whole/`
> (each the complete code of one student's solution, every file). Do not
> open, list or search anything outside `<stage>`, and do not run code. Judge
> each submission independently and ONLY on the principle «name» as the
> assignment states it: does the code violate it? Any other fault of the
> code does not count. Write a JSON list to `<stage>/verdicts.json`:
> `[{"id": "wNNN", "violates": true|false, "reason": "<one sentence>",
> "explanation": "<in Czech: what in the code breaks the principle and why
> it matters; empty when it does not>"}, …]`, one entry per file of
> `<stage>/whole/` (its name without `.md` is the id). Reply only with
> "done".
