# Target Report: target1

[Back to run index](../report.md)

## Metadata

- Target ID: target1
- Path: /mnt/c/Users/jiric/Documents/School/DP/PythonArchTesting/example/checkout_assignment/assignments/target1
- Exit Code: 0

## Summary

- Total Results: 15
- Status Counts: {'OK': 15}
- Severity Counts: {'error': 15}
- Category Counts: {'api_signature': 6, 'attribute_contract': 7, 'import_policy': 1, 'protocol_conformance': 1}

## Matching

- Total: 28
- Matched: 28
- Low confidence: 0
- Ambiguous: 0
- Unmatched: 0

## Results

| Project | Result ID | Category | Severity | Status | Rule | Source | Target | Location | Message |
|---|---|---|---|---|---|---|---|---|---|
| target1 | 78574581a55b7c3f | api_signature | error | OK | API001/required_entity_signature/v1 | checkout:CheckoutService.checkout | checkout:CheckoutService.checkout | checkout.py:23 | OK |
| target1 | 0a15ad16cd677616 | api_signature | error | OK | API001/required_entity_signature_return/v1 | checkout:CheckoutService.checkout | checkout:CheckoutService.checkout | checkout.py:23 | OK |
| target1 | e59454758e9a30b5 | api_signature | error | OK | API002/required_method/v1 | checkout:CheckoutService.checkout | checkout:CheckoutService.checkout | checkout.py:23 | OK |
| target1 | 7466a3ca66d125f6 | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Order | models:Order | models.py:66 | OK |
| target1 | 04ec720dc06a6187 | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Product | models:Product | models.py:18 | OK |
| target1 | 6b5eb87b228ed9bb | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Order | models:Order | models.py:66 | OK |
| target1 | 689ac316f942000c | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Product | models:Product | models.py:18 | OK |
| target1 | 29870e393cefee30 | attribute_contract | error | OK | API003/required_attribute/v1/d2 | models:Order | models:Order | models.py:66 | OK |
| target1 | 183add7b5e6a0c3e | attribute_contract | error | OK | API003/required_attribute/v1/d2 | models:Product | models:Product | models.py:18 | OK |
| target1 | 867d0e1f0f982d63 | attribute_contract | error | OK | API003/required_attribute/v1/d3 | models:Order | models:Order | models.py:66 | OK |
| target1 | d2702a1bdc841fa7 | api_signature | error | OK | API003/required_constructor/v1 | models:Product | models:Product | models.py:18 | OK |
| target1 | cfdedab77f3655cf | api_signature | error | OK | API004/required_factory/v1 | models:Cart.empty | models:Cart.empty | models.py:42 | OK |
| target1 | fc3cb3d53c740400 | api_signature | error | OK | API004/required_factory/v1 | models:Order.from_cart | models:Order.from_cart | models.py:90 | OK |
| target1 | e4e1b9a030542281 | import_policy | error | OK | DEP001/forbid_imports/v2 | storage:storage | storage:storage | storage/__init__.py:1 | OK |
| target1 | f8ec0b0869f005c5 | protocol_conformance | error | OK | PRO001/implements_protocol/v1 | storage.repository:InMemoryOrderRepository | storage.repository:InMemoryOrderRepository | storage/repository.py:16 | OK |
