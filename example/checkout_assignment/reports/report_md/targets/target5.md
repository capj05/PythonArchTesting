# Target Report: target5

[Back to run index](../report.md)

## Metadata

- Target ID: target5
- Path: /mnt/c/Users/jiric/Documents/School/DP/PythonArchTesting/example/checkout_assignment/assignments/target5
- Exit Code: 1

## Summary

- Total Results: 15
- Status Counts: {'FAILED': 3, 'OK': 11, 'SKIPPED': 1}
- Severity Counts: {'error': 14, 'warning': 1}
- Category Counts: {'api_signature': 6, 'attribute_contract': 7, 'import_policy': 1, 'protocol_conformance': 1}

## Matching

- Total: 28
- Matched: 14
- Low confidence: 0
- Ambiguous: 0
- Unmatched: 14

## Results

| Project | Result ID | Category | Severity | Status | Rule | Source | Target | Location | Message |
|---|---|---|---|---|---|---|---|---|---|
| target5 | 617ac00a309f1335 | api_signature | error | FAILED | API001/required_entity_signature/v1 | checkout:CheckoutService.checkout |  | checkout.py:23 | Required target entity missing or not matchable (status=unmatched, confidence=0.079929). |
| target5 | 643d2ef7732dbbe0 | api_signature | error | FAILED | API002/required_method/v1 | checkout:CheckoutService.checkout |  | checkout.py:23 | Required target entity missing or not matchable (status=unmatched, confidence=0.079929). |
| target5 | 61b8c934384c7c3f | protocol_conformance | error | FAILED | PRO001/implements_protocol/v1 | storage.repository:InMemoryOrderRepository |  | storage/repository.py:16 | Required target entity missing or not matchable (status=unmatched, confidence=0.0). |
| target5 | 947469e3141dd17a | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Order | models:Order | models.py:66 | OK |
| target5 | b7f7200143a8744b | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Product | models:Product | models.py:18 | OK |
| target5 | 02c7be940933c9ca | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Order | models:Order | models.py:66 | OK |
| target5 | d0b241e748099f5e | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Product | models:Product | models.py:18 | OK |
| target5 | 8c5d97c9a7498ac2 | attribute_contract | error | OK | API003/required_attribute/v1/d2 | models:Order | models:Order | models.py:66 | OK |
| target5 | 86e1ac0ef0547c0b | attribute_contract | error | OK | API003/required_attribute/v1/d2 | models:Product | models:Product | models.py:18 | OK |
| target5 | f4b2aff71ddc7605 | attribute_contract | error | OK | API003/required_attribute/v1/d3 | models:Order | models:Order | models.py:66 | OK |
| target5 | c68ad207f8e7dce4 | api_signature | error | OK | API003/required_constructor/v1 | models:Product | models:Product | models.py:18 | OK |
| target5 | 3c1f5b6096452650 | api_signature | error | OK | API004/required_factory/v1 | models:Cart.empty | models:Cart.empty | models.py:42 | OK |
| target5 | bdbe910f309c7365 | api_signature | error | OK | API004/required_factory/v1 | models:Order.from_cart | models:Order.from_cart | models.py:90 | OK |
| target5 | 6331e497e8ac915b | import_policy | error | OK | DEP001/forbid_imports/v2 | storage:storage |  | storage/__init__.py:1 | OK |
| target5 | e534fb1addda3354 | api_signature | warning | SKIPPED | API001/required_entity_signature_return/v1 | checkout:CheckoutService.checkout |  | checkout.py:23 | Rule skipped due to matching status unmatched (confidence=0.079929). |
