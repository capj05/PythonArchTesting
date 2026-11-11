# M6: the teaching workflow, evaluated

The pilot (`../pilot/`) measured the tool's verdicts. M6 measures the
teaching workflow the MCP server offers a teacher's AI, with agents in the
teacher's and the students' places:

- **VO3, the AI prepares a task.** Per principle, 3 runs (Sonnet): the agent
  gets the catalogue entry (`describe_principle`), the unannotated reference,
  and `describe_principle`, `describe_marker` and `prepare_task` through
  `tools.py`, and writes `task.toml`. Measured: `accepted`, the number of
  problems, whether the task is a copy of the example's, and how the tool with
  the agent's task does on the pilot's injected errors, defects and carriers,
  beside the principle's own task on the same data.
- **VO5, explanations.** For 12 errors the tool finds (6 per principle), an
  agent writes the student's explanation from `explain_target` with the
  principle; another agent rates where, which principle and why (0-2 each),
  and 6 of the explanations (3 per principle) go to the owner for review.
- **Realistic code.** 6 solutions without a skeleton, evaluated with the
  principle's own task and judged by an LLM as in the pilot. "Realistic code"
  means exactly: the pilot's S-text condition (the assignment text, no
  skeleton), plus packages named as students submit them
  (`<ident>_<surname>`), plus, for 2 of the 6 solutions, modules importing
  their siblings absolutely (`--absolute-imports`).

No script here runs an agent; the leader does, with the prompts below.

## Layout

```
m6/
  tools.py     the agents' access to the MCP tools' functions (JSON out)
  stage.py     staging of every role, and collect
  harness.py   shared by stage.py and score.py
  score.py     writes results-vo3-vo5.md and results-vo3-vo5.csv
  selftest.py  the harness end to end on fake agent outputs
  results/                                  versioned (small)
    tasks/<p>/run-<N>/task.toml              the authors' tasks
    explanations/<p>/<submission>.md         the explainers' texts
    ratings/<p>/<submission>.json            the raters' scores
    judgments/<run>/<p>.json                 the judges on the realistic code
  data/                                     not versioned (.gitignore)
    solutions/<p>/<ident_surname>/           the realistic solutions
    meta/<p>/<ident_surname>.json            absolute imports asked for or not
    findings/<p>/<submission>.json           what each explainer read
    reports/                                 the tool's reports
  results-vo3-vo5.md  results-vo3-vo5.csv
```

`<submission>` of VO5 is a pilot injected error (`<id>-<carrier_>`, the
directory under `../pilot/<p>/injected/err/`) or a realistic solution. VO3
reads the pilot's `key.json` and its unversioned `solutions/` and
`injected/`.

## Tools

```
python example/principles/m6/tools.py describe <principle>
python example/principles/m6/tools.py describe_marker <name>
python example/principles/m6/tools.py prepare <task_dir>
python example/principles/m6/tools.py evaluate <task_dir> <targets_dir> [--out DIR]
python example/principles/m6/tools.py explain <report.json> <target> <principle>
```

They call the functions behind the MCP tools `describe_principle`,
`describe_marker`, `prepare_task`, `run_evaluation` (dynamic, `bwrap`)
followed by `class_overview`, and `explain_target(principle=...)`, and print
one line of JSON; a refused input prints `{"error": ...}` and exits 2. The
author agent gets only `describe`, `describe_marker` and `prepare`, as
command lines with absolute paths in its stage's `tools.txt`, each under the
description an MCP client sees for its tool, after the server's
instructions. It learns the task format and the case language (`$new`,
`steps`, ...) from exactly what a real MCP client sees: the description of
`prepare_task` carries the `task.toml` format and points to
`describe_marker` for the case language.

## Staging

As in the pilot, no agent works in the repository: `stage.py` writes exactly
the inputs of a role into a fresh directory and prints its path (`<stage>`);
the agent reads and writes only there; `stage.py collect <stage>` validates
the output and copies it into the layout. What a stage is for is kept beside
it in `<stage>.stage.json`, and the report the explainer's findings come from
in `<stage>.report/`; staging writes nothing into the repository. Stages go
under `$PAT_STAGE_ROOT` when it is set, else under the pilot's stage root, as
`m6-<role>-<p>-<n>/` (or `--out DIR`).

| Role | `<stage>` holds | The agent writes | `collect` puts it to |
|---|---|---|---|
| `author <p> --run N` | `principle.json`, `task/reference/`, `tools.txt` | `task/task.toml` | `results/tasks/<p>/run-N/task.toml` (valid TOML, principle `<p>`, reference unchanged) |
| `explainer <p> <submission>` | `principle.json`, `findings.json`, `code/` | `explanation.md` | `collect --model M`: `results/explanations/<p>/<submission>.md` and `<submission>.json` (`{"model": M}`); findings to `data/findings/` |
| `rater <p> <submission>` | `principle.json`, `code/`, `explanation.md`, `rubric.md` | `rating.json` | `collect --model M`: `results/ratings/<p>/<submission>.json` (scores 0-2, a comment, `model` M) |
| `solver <p> --student S [--absolute-imports]` | `assignment.md` (the pilot's), `submission.txt` | `S/` | `data/solutions/<p>/S/` (files that parse; with `--absolute-imports` a sibling imported by plain name) + `data/meta/<p>/S.json` |
| `judge <p> --run <model>-<n>` | `assignment.md`, `whole/S.md` per realistic solution | `verdicts.json` | `results/judgments/<run>/<p>.json` (one valid entry per solution) |

The explainer's `findings.json` is `explain_target` with the principle, from
a fresh run of the principle's own task on the submission alone (named
`submission`, or the student's name), or from `--report <report.json>`; a
submission the tool does not fail is refused. `principle.json` of the
explainer and the rater is the principle's `name`, `summary` and `why`
(`describe_principle`). `submission.txt` asks for the package `S/` with
`__init__.py`, or, with `--absolute-imports`: "Import sibling modules by
their plain name (`import inventory` / `from inventory import Inventory`), as
you do when you run the code from inside its folder; this overrides the
import style shown in the assignment", `__init__.py` optional; `collect` then
requires a module importing a sibling by its plain name. `collect` replaces
an existing destination only with `--force`.

## Procedure (M6b)

All commands from the worktree root with its venv. Every agent step is
`stage.py <role> ...`, a fresh agent with the prompt below and `<stage>`
the printed path, then `stage.py collect <stage>`. At most 3 agents at once.

1. **VO3, authors** (Sonnet, prompt A), 6 agents:
   `stage.py author <p> --run N` for `<p>` in `encapsulation`,
   `io_separation` and `N` in 1, 2, 3. The agent improves its task until
   `prepare` reports it accepted or until it has run `prepare` 5 times, then
   stops (prompt A).
2. **Realistic code, solvers** (prompt S), 6 agents, one per solution:
   `encapsulation`: `stage.py solver encapsulation --student novj01_novak`,
   `--student dvop02_dvorak`, `--student svoe03_svoboda --absolute-imports`;
   `io_separation`: `--student kral04_kral`, `--student horm05_horak`,
   `--student vesk06_vesely --absolute-imports`. The model of each is the
   leader's choice; note it.
3. **Realistic code, judges** (Sonnet, prompt J):
   `stage.py judge <p> --run sonnet-1` for both principles.
4. **VO5, explainers** (Sonnet, prompt X): `stage.py candidates <p>` prints
   the pilot's injected errors the principle's own task fails, in an order
   seeded by 7; take the first 6 of each principle
   (`encapsulation`: `mutate_container-skeleton_opus-1`,
   `bypass_method-skeleton_opus-1`, `replace_attribute-skeleton_opus-1`,
   `replace_attribute-skeleton_sonnet-1`, `replace_attribute-skeleton_haiku-1`,
   `bypass_method-skeleton_haiku-1`; `io_separation`: its 6 detected ones,
   `input_in_logic-*` and `print_instead_of_return-*`, as of 2026-11-06), then
   `stage.py explainer <p> <submission>` for each; collect with
   `stage.py collect <stage> --model <the explainer's model>`.
5. **VO5, raters** (prompt R, a model other than the explainer's):
   `stage.py rater <p> <submission>` for each explanation collected; collect
   with `stage.py collect <stage> --model <the rater's model>`.
6. **Score.** `python example/principles/m6/score.py` writes
   `results-vo3-vo5.md` and `.csv`: VO3 per principle and task (`example`,
   `run-N`): `accepted`, problems, errors flagged, flagged as the injected
   error, defects flagged (FP), carriers flagged, unmatched (failed only for
   a missing required entity, no verdict on the principle) and not judged,
   denominators after the slash, and `copied example` (the task's TOML data
   is the example's); VO5 per explanation with the explainer's and the
   rater's model (`same model` flags a rating by the explainer's own model)
   and the means, and 6 for the owner (3 per principle, the first 3 in an
   order seeded by 7); realistic code per solution with `class_overview`
   (verdict, error ids) and each judge run's verdict. It exits 1, writing
   nothing, when an input is missing (fewer than 3 runs per principle, 6
   explanations per principle, 6 solutions; a rating without its explanation
   or the other way round; a model not recorded; no judge run, or a judge
   without a verdict on a solution) or a cell would be empty.

`python example/principles/m6/selftest.py` runs every stage and collect on
fake agent outputs in a temporary directory (the principle's own task as an
author's, a broken one, two solutions from the catalogue's `ok_basic` under
student names, one with absolute imports and no `__init__.py`, fake
explanations, ratings and verdicts with their models) against a fake pilot
built as the pilot's self-test builds it, then `score.py`: no empty cell, the
known counts, the copied example flagged, the refusals (including no judge
run), and the repository unchanged.

## Prompts

`<stage>` is the absolute path `stage.py` printed for this agent; `<p>` the
principle's id; `S` the student's package name.

**A — task author** (role `author`):

> You are a teacher of an introductory Python course. You prepare an
> automatically checked task that practises one principle of a teaching
> tool's catalogue, `<p>`, for a model solution you already have. Your
> working directory is `<stage>`. Read ONLY the files in it:
> `<stage>/principle.json` (the principle's catalogue entry: what it means,
> the roles of a task's code, the checks, the typical errors),
> `<stage>/tools.txt` (the three tools you may run and what they do) and the
> model solution in `<stage>/task/reference/` (all files). Do not open, list
> or search anything outside `<stage>`, do not change anything in
> `<stage>/task/reference/`, and run no command other than the three in
> `<stage>/tools.txt`. Write the task into `<stage>/task/task.toml`: the
> principle, every role of the principle bound to the model solution's code,
> and the cases the checks run. Check it with the `prepare` command and
> improve it until `prepare` reports it accepted or until you have run
> `prepare` 5 times, then stop. Reply only with the last `accepted` value
> and one sentence on any problem left.

**S — solver** (role `solver`; the pilot's S-text, with the package named
after the student):

> You are a student solving a programming assignment. Your working directory
> is `<stage>`. Read ONLY `<stage>/assignment.md` and
> `<stage>/submission.txt`. Do not open, list or search anything outside
> `<stage>`. Write your complete solution into the directory `<stage>/S/`
> (create it) as `submission.txt` says. Organise the modules as you see fit.
> Do not execute any code. Reply only with the list of files you wrote.

**J — judge** (role `judge`; the pilot's prompt J, with the student's
package name as the id):

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

«name» is the principle's `name` from `describe_principle` (`tools.py
describe <p>`).

**X — explainer** (role `explainer`):

> You are a teaching assistant of an introductory Python course. An
> automatic checker found a mistake in a student's solution. Your working
> directory is `<stage>`. Read ONLY `<stage>/findings.json` (the checker's
> result for this solution: each violation with its typical error, `what`
> happened and its facts, and once per error its title, why and fix),
> `<stage>/principle.json` (the principle the code was checked for: its
> `name`, `summary` and `why`) and the student's code in `<stage>/code/` (all
> files). Do not open, list or search anything outside `<stage>`, and do not
> run code. Write to the student, in Czech, into `<stage>/explanation.md`, at
> most 150 words: where in the code the mistake is (file, function, line),
> which principle it breaks (by its name) and what that principle asks, why
> it is a problem in this code, and how to fix it.
> Say only what the findings and the code support. Reply only with "done".

**R — rater** (role `rater`):

> You check explanations a teaching assistant wrote to students about a
> mistake in their code. Your working directory is `<stage>`. Read ONLY
> `<stage>/rubric.md`, `<stage>/principle.json` (the principle the code was
> checked for), `<stage>/explanation.md` and the student's code in
> `<stage>/code/` (all files). Do not open, list or search anything outside
> `<stage>`, and do not run code. Rate the explanation by the rubric,
> checking each of its claims against the code. Write
> `<stage>/rating.json`: `{"location": 0|1|2, "principle": 0|1|2,
> "reason": 0|1|2, "comment": "<one or two sentences: what is wrong; empty
> when nothing is>"}`. Reply only with "done".
