# Architecture

This is the current high-level pipeline for PythonArchTesting.

## Pipeline

1. CLI orchestration starts in `pythonarchtesting.cli`.
2. Source entities and declaration metadata are extracted from the reference
   project in `pythonarchtesting.entities_extraction`.
3. Declaration entries are normalized and compiled into rules in
   `pythonarchtesting.rules.compilation`.
4. Source entities are matched to target entities in `pythonarchtesting.matching`.
5. Compiled rules are evaluated in `pythonarchtesting.execution.evaluators`.
6. Reports are built and rendered in `pythonarchtesting.report`.

For multi-target runs, `pythonarchtesting.runner_multi` prepares the shared source state once
and evaluates each target separately.

## Key Modules

### Declaration Surface

- `pythonarchtesting.rules`
- `pythonarchtesting.rules.declaration.core`

`pythonarchtesting.rules` is the public import surface for marker factories. Add or change
user-facing declaration helpers here.

### Extraction And Normalization

- `pythonarchtesting.entities_extraction.annotations`
- `pythonarchtesting.rules.compilation.declarations`

This layer parses annotation metadata, validates supported shapes, and
normalizes them into shared declaration entries.

### Rule Compilation

- `pythonarchtesting.rules.compilation.orchestrator`
- `pythonarchtesting.rules.compilation.decorators.api_signature`
- `pythonarchtesting.rules.compilation.decorators.import_policy`
- `pythonarchtesting.rules.compilation.decorators.protocols`
- `pythonarchtesting.rules.compilation.decorators.flow`

Compilation turns normalized declarations into rule objects, compiler evidence,
and compiler-side results.

### Matching

- `pythonarchtesting.matching.engine`
- `pythonarchtesting.matching.candidates`
- `pythonarchtesting.matching.models`

Matching chooses the best target entity for each source entity and records
confidence and candidate details for reporting.

### Evaluation

- `pythonarchtesting.execution.evaluators.api_signature`
- `pythonarchtesting.execution.evaluators.import_policy`
- `pythonarchtesting.execution.evaluators.protocol_conformance`
- `pythonarchtesting.execution.evaluators.variable_flow`
- `pythonarchtesting.execution.evaluators.registry`

Each evaluator owns one rule family and produces result rows with messages, fix
hints, evidence, and status.

### Reporting

- `pythonarchtesting.report.api`
- `pythonarchtesting.report.ir`
- `pythonarchtesting.report.renderers`

Reporting converts run state into a stable report structure, then renders JSON
or Markdown.

## Where To Extend Features

To add a new declaration-driven rule:

1. expose a marker in `pythonarchtesting.rules` and `pythonarchtesting.rules.declaration.core`
2. teach extraction and normalization to accept it
3. add a compiler in `pythonarchtesting.rules.compilation`
4. add an evaluator and register it in
   `pythonarchtesting.execution.evaluators.registry`
5. verify report output and docs

To change reporting behavior:

1. update report assembly in `pythonarchtesting.report.api` or `pythonarchtesting.report.ir`
2. update renderers in `pythonarchtesting.report.renderers`
3. keep JSON and Markdown expectations aligned
