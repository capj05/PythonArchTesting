# SonarQube architecture analysis on the architectural mutants (E5, T6)

SonarQube Server (2026.4+) compares an *intended architecture* (containers
and the relations allowed between siblings) with the code and raises an
issue for each deviation. The feature is in the commercial editions only;
without a licence the server accepts an analysis but does not process it
("Analyses suspended … LICENSING", tried 2026-10-31). `sonar.py` runs the
whole comparison once a 14-day trial licence of the Developer edition is at
hand, so the trial is not spent on setting up.

## What is compared

- **Variants:** the same as E1/E5: hand-written and held-out mutants and
  equivalent rewrites of programs 1–3 (162 in all), applied by the mutant
  harness's own `_apply`.
- **Intended architecture:** derived from each reference's `enforce_layers`
  marker, as the import-linter contracts of E5 are (`intended-architecture.md`,
  written by `sonar.py plan`): a layer may use the layers below it but not
  past a closed one; the modules of one layer are independent. SonarQube
  documents no file or Web API for the intended architecture, only the UI, so
  it is entered by hand once per program.
- **Caught:** a variant's branch has an architecture issue the unchanged
  solution (the main branch) does not have. The rule keys of deviations are
  not documented: `collect` counts issues whose rule key contains
  "architecture" and keeps every issue per branch under `.state/issues/` —
  check the filter against those after the first variant (step 5).

## Steps

From the repository root, with `docker`; the server listens on
`127.0.0.1:9000` only.

1. `python example/sonarqube/sonar.py up` — start `sonarqube:developer`.
2. `SONAR_LICENSE=<key> python example/sonarqube/sonar.py init` — sets a new
   admin password, the licence and an analysis token. They are stored in
   `.state/server.json` (mode 600, git-ignored) and never printed; the licence
   is read only from the environment. Prefix the command with a space (or read
   the key from a password manager) so the key stays out of the shell
   history.
3. `python example/sonarqube/sonar.py plan`, then
   `python example/sonarqube/sonar.py scan --base` — create the projects
   `pat-program1..3` and analyse each unchanged solution as the main branch.
4. In the UI (`http://127.0.0.1:9000`, user `admin`, the password from step 2
   in `.state/server.json`), for each project: Architecture → Intended
   architecture, enter the containers and allowed relations of
   `intended-architecture.md`, Save.
5. Check the set-up on one variant first:
   `python example/sonarqube/sonar.py scan --program program1 --only M02`,
   then `collect`, and look at `.state/issues/pat-program1-hand-M02.json`:
   M02 (the controller imports the repository) must show a deviation. If its
   rule key does not contain "architecture", adjust `_architectural`.
6. `python example/sonarqube/sonar.py scan` — every variant as a branch
   (162 analyses; a few minutes each with the scanner image).
7. `python example/sonarqube/sonar.py collect` → `results.md`, `results.csv`.
8. `python example/sonarqube/sonar.py down` — remove the container (the
   images stay).

## Assumptions to confirm with the licence

- An intended architecture entered for a project applies to its branches
  (branch analysis is in the Developer edition) [unverified].
- A Python module file and a package directory under `src/` can be
  containers of their own [unverified; the docs say only that files are
  grouped by their folders and modules].
- The scanner image reaches the server through `--network host`.
