# Target Report: target2

[Back to run index](../report.md)

## Metadata

- Target ID: target2
- Path: /mnt/c/Users/jiric/Documents/School/DP/PythonArchTesting/example/checkout_assignment/assignments/target2
- Exit Code: 1

## Summary

- Total Results: 15
- Status Counts: {'FAILED': 3, 'OK': 12}
- Severity Counts: {'error': 15}
- Category Counts: {'api_signature': 6, 'attribute_contract': 7, 'import_policy': 1, 'protocol_conformance': 1}

## Matching

- Total: 28
- Matched: 26
- Low confidence: 2
- Ambiguous: 0
- Unmatched: 0

## Results

| Project | Result ID | Category | Severity | Status | Rule | Source | Target | Location | Message |
|---|---|---|---|---|---|---|---|---|---|
| target2 | dcd965061fa9beeb | api_signature | error | FAILED | API001/required_entity_signature_return/v1 | checkout:CheckoutService.checkout | checkout:CheckoutService.checkout | checkout.py:23 | Required return annotation mismatch for checkout:CheckoutService.checkout: return annotation mismatch: expected models.Order, found dict |
| target2 | fe0aedd0dc2e6774 | attribute_contract | error | FAILED | API003/required_attribute/v1/d2 | models:Order | models:Order | models.py:66 | Required attribute mismatch for models:Order: missing required attribute 'total' |
| target2 | 88a4a6ad82693a2e | api_signature | error | FAILED | API003/required_constructor/v1 | models:Product | models:Product | models.py:18 | Required constructor mismatch for models:Product: missing parameter 'sku' |
| target2 | 34d70e474167e7d2 | api_signature | error | OK | API001/required_entity_signature/v1 | checkout:CheckoutService.checkout | checkout:CheckoutService.checkout | checkout.py:23 | OK |
| target2 | 10a4e0b17d41aaa5 | api_signature | error | OK | API002/required_method/v1 | checkout:CheckoutService.checkout | checkout:CheckoutService.checkout | checkout.py:23 | OK |
| target2 | 1adad4cad33885b7 | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Order | models:Order | models.py:66 | OK |
| target2 | 0cf7a1b8fd943d5c | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Product | models:Product | models.py:18 | OK |
| target2 | aaf6ae9e5021f2f1 | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Order | models:Order | models.py:66 | OK |
| target2 | 4de38126a52ef921 | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Product | models:Product | models.py:18 | OK |
| target2 | 922759ecc9612dd6 | attribute_contract | error | OK | API003/required_attribute/v1/d2 | models:Product | models:Product | models.py:18 | OK |
| target2 | e2bcd96b8421e165 | attribute_contract | error | OK | API003/required_attribute/v1/d3 | models:Order | models:Order | models.py:66 | OK |
| target2 | 8ba93f01b4001339 | api_signature | error | OK | API004/required_factory/v1 | models:Cart.empty | models:Cart.empty | models.py:42 | OK |
| target2 | 632e560a50b3bc68 | api_signature | error | OK | API004/required_factory/v1 | models:Order.from_cart | models:Order.from_cart | models.py:90 | OK |
| target2 | 102a342684c3edff | import_policy | error | OK | DEP001/forbid_imports/v2 | storage:storage | storage:storage | storage/__init__.py:1 | OK |
| target2 | cdc7dc46ae9a2bdb | protocol_conformance | error | OK | PRO001/implements_protocol/v1 | storage.repository:InMemoryOrderRepository | storage.repository:InMemoryOrderRepository | storage/repository.py:16 | OK |
