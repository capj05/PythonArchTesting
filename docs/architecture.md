# Architecture

This is the current high-level pipeline for PythonArchTesting.

## Pipeline

1. CLI orchestration starts in `src.cli`.
2. Source entities and declaration metadata are extracted from the reference
   project in `src.entities_extraction`.
3. Declaration entries are normalized and compiled into rules in
   `src.rules.compilation`.
4. Source entities are matched to target entities in `src.matching`.
5. Compiled rules are evaluated in `src.execution.evaluators`.
6. Reports are built and rendered in `src.report`.

For multi-target runs, `src.runner_multi` prepares the shared source state once
and evaluates each target separately.

## Key Modules

### Declaration Surface

- `src.rules`
- `src.rules.declaration.core`

`src.rules` is the public import surface for marker factories. Add or change
user-facing declaration helpers here.

### Extraction And Normalization

- `src.entities_extraction.annotations`
- `src.rules.compilation.declarations`

This layer parses annotation metadata, validates supported shapes, and
normalizes them into shared declaration entries.

### Rule Compilation

- `src.rules.compilation.orchestrator`
- `src.rules.compilation.decorators.api_signature`
- `src.rules.compilation.decorators.import_policy`
- `src.rules.compilation.decorators.protocols`
- `src.rules.compilation.decorators.flow`

Compilation turns normalized declarations into rule objects, compiler evidence,
and compiler-side results.

### Matching

- `src.matching.engine`
- `src.matching.candidates`
- `src.matching.models`

Matching chooses the best target entity for each source entity and records
confidence and candidate details for reporting.

### Evaluation

- `src.execution.evaluators.api_signature`
- `src.execution.evaluators.import_policy`
- `src.execution.evaluators.protocol_conformance`
- `src.execution.evaluators.variable_flow`
- `src.execution.evaluators.registry`

Each evaluator owns one rule family and produces result rows with messages, fix
hints, evidence, and status.

### Reporting

- `src.report.api`
- `src.report.ir`
- `src.report.renderers`

Reporting converts run state into a stable report structure, then renders JSON
or Markdown.

## Where To Extend Features

To add a new declaration-driven rule:

1. expose a marker in `src.rules` and `src.rules.declaration.core`
2. teach extraction and normalization to accept it
3. add a compiler in `src.rules.compilation`
4. add an evaluator and register it in
   `src.execution.evaluators.registry`
5. verify report output and docs

To change reporting behavior:

1. update report assembly in `src.report.api` or `src.report.ir`
2. update renderers in `src.report.renderers`
3. keep JSON and Markdown expectations aligned
