# Core Components

## Declaration

- `pythonarchtesting.rules`
- `pythonarchtesting.rules.declaration.core`

`pythonarchtesting.rules` is the public entry point for annotation markers. These modules expose only the supported declaration intent layer.

## Compilation

- `pythonarchtesting.rules.compilation.compile_rules`
- `pythonarchtesting.rules.compilation.decorators.api_signature`
- `pythonarchtesting.rules.compilation.decorators.import_policy`
- `pythonarchtesting.rules.compilation.decorators.protocols`

Compilation is annotation-driven. The canonical compiler namespace is `pythonarchtesting.rules.compilation`, which normalizes signature-level and `__archtest__: Annotated[...]` declarations into shared declaration entries and dispatches them through rule-family compiler modules. `pythonarchtesting.core.compilation` remains available only as a compatibility facade.

## Execution

- `pythonarchtesting.runner`
- `pythonarchtesting.execution.evaluators.api_signature`
- `pythonarchtesting.execution.evaluators.import_policy`
- `pythonarchtesting.execution.evaluators.protocol_conformance`

## Reporting

- `pythonarchtesting.report.api`
- `pythonarchtesting.report.ir.from_state`
