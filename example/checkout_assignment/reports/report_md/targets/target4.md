# Target Report: target4

[Back to run index](../report.md)

## Metadata

- Target ID: target4
- Path: /mnt/c/Users/jiric/Documents/School/DP/PythonArchTesting/example/checkout_assignment/assignments/target4
- Exit Code: 1

## Summary

- Total Results: 15
- Status Counts: {'FAILED': 3, 'OK': 11, 'SKIPPED': 1}
- Severity Counts: {'error': 14, 'warning': 1}
- Category Counts: {'api_signature': 6, 'attribute_contract': 7, 'import_policy': 1, 'protocol_conformance': 1}

## Matching

- Total: 28
- Matched: 22
- Low confidence: 3
- Ambiguous: 0
- Unmatched: 3

## Results

| Project | Result ID | Category | Severity | Status | Rule | Source | Target | Location | Message |
|---|---|---|---|---|---|---|---|---|---|
| target4 | 3eb054b812f0098d | api_signature | error | FAILED | API001/required_entity_signature/v1 | checkout:CheckoutService.checkout |  | checkout.py:23 | Required target entity missing or not matchable (status=low_confidence, confidence=0.7). |
| target4 | 873e92652c3bd881 | api_signature | error | FAILED | API002/required_method/v1 | checkout:CheckoutService.checkout |  | checkout.py:23 | Required target entity missing or not matchable (status=low_confidence, confidence=0.7). |
| target4 | 9846a503c07429ab | protocol_conformance | error | FAILED | PRO001/implements_protocol/v1 | storage.repository:InMemoryOrderRepository |  | storage/repository.py:16 | Required target entity missing or not matchable (status=unmatched, confidence=0.0). |
| target4 | 7e83151de5b92f67 | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Order | models:Order | models.py:66 | OK |
| target4 | b6859173145a0bcb | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Product | models:Product | models.py:18 | OK |
| target4 | 0f2c033f89a93896 | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Order | models:Order | models.py:66 | OK |
| target4 | 3ff56a7271b4e9b6 | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Product | models:Product | models.py:18 | OK |
| target4 | 62b44478c114d316 | attribute_contract | error | OK | API003/required_attribute/v1/d2 | models:Order | models:Order | models.py:66 | OK |
| target4 | caa58c5548ea3a2d | attribute_contract | error | OK | API003/required_attribute/v1/d2 | models:Product | models:Product | models.py:18 | OK |
| target4 | a972d99020b1db6e | attribute_contract | error | OK | API003/required_attribute/v1/d3 | models:Order | models:Order | models.py:66 | OK |
| target4 | ed2c18f87c3de084 | api_signature | error | OK | API003/required_constructor/v1 | models:Product | models:Product | models.py:18 | OK |
| target4 | 6277ee188354a804 | api_signature | error | OK | API004/required_factory/v1 | models:Cart.empty | models:Cart.empty | models.py:42 | OK |
| target4 | dc84d4096ed027fc | api_signature | error | OK | API004/required_factory/v1 | models:Order.from_cart | models:Order.from_cart | models.py:90 | OK |
| target4 | b5472d69aacb78b4 | import_policy | error | OK | DEP001/forbid_imports/v2 | storage:storage | storage:storage | storage/__init__.py:1 | OK |
| target4 | 9664a29d3e26af62 | api_signature | warning | SKIPPED | API001/required_entity_signature_return/v1 | checkout:CheckoutService.checkout |  | checkout.py:23 | Rule skipped due to matching status low_confidence (confidence=0.7). |
