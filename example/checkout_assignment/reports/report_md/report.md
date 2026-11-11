# Validation Run Report

**Generated:** 2026-11-10T20:09:53.104551Z
**Framework:** 0.1.0
**Source:** example/checkout_assignment/reference
**Mode:** static-only
**Exit Code:** 1

## Run Summary

- Targets total: 5
- Targets passed: 1
- Targets failed: 4

## Result Totals

- Total Results: 75
- Status Counts: FAILED: 11 · OK: 62 · SKIPPED: 2
- Severity Counts: error: 73 · warning: 2
- Category Counts: api_signature: 30 · attribute_contract: 35 · import_policy: 5 · protocol_conformance: 5

## Top Rules by Violation Count

| Rule | Violations |
|---|---|
| PRO001/implements_protocol/v1 | 3 |
| API001/required_entity_signature/v1 | 2 |
| API002/required_method/v1 | 2 |
| API001/required_entity_signature_return/v1 | 1 |
| API003/required_attribute/v1/d2 | 1 |

## Top Source Files

| File | Results |
|---|---|
| models.py | 50 |
| checkout.py | 15 |
| storage/__init__.py | 5 |
| storage/repository.py | 5 |

## Targets

| Target | Path | Exit | Results | Failed |
|---|---|---|---|---|
| [target1](targets/target1.md) | example/checkout_assignment/assignments/target1 | 0 | 15 | 0 |
| [target2](targets/target2.md) | example/checkout_assignment/assignments/target2 | 1 | 15 | 3 |
| [target3](targets/target3.md) | example/checkout_assignment/assignments/target3 | 1 | 15 | 2 |
| [target4](targets/target4.md) | example/checkout_assignment/assignments/target4 | 1 | 15 | 3 |
| [target5](targets/target5.md) | example/checkout_assignment/assignments/target5 | 1 | 15 | 3 |
