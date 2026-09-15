# Example Project 1

This example is a compact rule showcase for PythonArchTesting. It is not meant
to look like a real application. Every module, class, and function in
`reference/` exists only to demonstrate one of the maintained declaration
families and how different target submissions appear in reports.

## What The Reference Demonstrates

The reference project models a tiny submission workflow:

- `contracts.py`
  Defines `SubmissionRepository`, the protocol used by protocol checks.
- `workflow.py`
  Defines `normalize_submission(...)` with
  `required_entity_signature(...)` and statement-level `flow(...)` /
  `enforce_flow(...)`.
- `workflow.py`
  Defines `prepare_repository(...)` with signature-level
  `implements_protocol(...)`.
- `workflow.py`
  Defines `SubmissionService.save_draft(...)` and
  `SubmissionService.publish(...)` with `required_method(...)`.
- `models.py`
  Defines `DraftSubmission` with `required_attribute(...)`,
  `required_constructor(...)`, `required_factory(...)`,
  `does_not_have(...)`, and `subclass_of(...)`.
- `storage/__init__.py`
  Declares `forbid_imports("requests", scope="package", package="storage")`.
- `storage/repository.py`
  Declares `MemorySubmissionRepository` with class-level
  `implements_protocol("reference.contracts.SubmissionRepository")`.

The resulting reports include these rule families:

- `API001/required_entity_signature`
- `API001/required_entity_signature_return`
- `API002/required_method`
- `API003/required_attribute`
- `API003/required_constructor`
- `API004/required_factory`
- `DEP001/forbid_imports/v2`
- `FLW001/enforce_flow/v1`
- `NEG001/does_not_have/v1`
- `NOM001/subclass_of/v1`
- `PRO001/implements_protocol/v1`
- `PRO002/implements_protocol_signature/v1`

## Target Variations

Each assignment is shaped to demonstrate a specific reporting pattern:

- `target1`
  Fully correct submission. Every result is `OK`.
- `target2`
  Same structure as the reference, but with signature, attribute, and
  constructor mistakes. This shows matched entities with explicit mismatch
  messages.
- `target3`
  Same structure as the reference, but with a reachable forbidden import and
  protocol violations. This shows rule failures without matching ambiguity.
- `target4`
  Same idea, different names. This stresses matching diagnostics and produces
  `unmatched`, `low_confidence`, and skipped dependent rules in the workflow
  layer while the class-focused rules still pass.
- `target5`
  Skeletal partial submission. This shows missing-entity style failures without
  declaration-validation errors while the class-focused rules still pass.

## Run The Example

Validate the reference declarations first:

```bash
python -m pythonarchtesting.cli --validate-declarations --source example/project_1/reference --format json
```

Run all targets and write JSON. The CLI does not create the output directory,
so make it first:

```bash
mkdir -p example/project_1/reports
python -m pythonarchtesting.cli --source example/project_1/reference --targets-dir example/project_1/assignments --format json --output example/project_1/reports/report.json
```

Generate a Markdown bundle with target pages. Detail level comes from
`[report].markdown_detail` in the config file (`verbose` is the default):

```bash
python -m pythonarchtesting.cli --source example/project_1/reference --targets-dir example/project_1/assignments --format markdown --output example/project_1/reports/report_md
```

## How To Read The Reports

Read the outputs in this order:

1. run-level `summary`
2. per-target `summary`
3. failing `results`
4. `matching` details for missing or weak matches

Look for:

- `rule_id`
- `status`
- `severity`
- `message`
- `details.match_status`
- `fix_hints`

Use this example when you want to explain the difference between:

- direct signature mismatches
- protocol failures
- forbidden import failures
- unmatched entities
- low-confidence matches
- skipped dependent checks
