# Core Components

## Declaration

- `src.rules`
- `src.rules.declaration.core`

`src.rules` is the public entry point for annotation markers. These modules expose only the supported declaration intent layer.

## Compilation

- `src.rules.compilation.compile_rules`
- `src.rules.compilation.decorators.api_signature`
- `src.rules.compilation.decorators.import_policy`
- `src.rules.compilation.decorators.protocols`

Compilation is annotation-driven. The canonical compiler namespace is `src.rules.compilation`, which normalizes signature-level and `__archtest__: Annotated[...]` declarations into shared declaration entries and dispatches them through rule-family compiler modules. `src.core.compilation` remains available only as a compatibility facade.

## Execution

- `src.runner_multi`
- `src.execution.evaluators.api_signature`
- `src.execution.evaluators.import_policy`
- `src.execution.evaluators.protocol_conformance`

## Reporting

- `src.report.api`
- `src.report.ir.from_state`
