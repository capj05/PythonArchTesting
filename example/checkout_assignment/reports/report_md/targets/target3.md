# Target Report: target3

[Back to run index](../report.md)

## Metadata

- Target ID: target3
- Path: /mnt/c/Users/jiric/Documents/School/DP/PythonArchTesting/example/checkout_assignment/assignments/target3
- Exit Code: 1

## Summary

- Total Results: 15
- Status Counts: {'FAILED': 2, 'OK': 13}
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
| target3 | 91989f65c9735deb | import_policy | error | FAILED | DEP001/forbid_imports/v2 | storage:storage | storage:storage | storage/__init__.py:1 | DEP001 reachable forbidden import paths found in package 'storage': ['requests'] (2 paths) |
| target3 | e49bc5236f20effa | protocol_conformance | error | FAILED | PRO001/implements_protocol/v1 | storage.repository:InMemoryOrderRepository | storage.repository:InMemoryOrderRepository | storage/repository.py:16 | Protocol conformance mismatch for storage.repository:InMemoryOrderRepository: save: return annotation mismatch: expected models.Order, found bool |
| target3 | 9baed89f60fd81d5 | api_signature | error | OK | API001/required_entity_signature/v1 | checkout:CheckoutService.checkout | checkout:CheckoutService.checkout | checkout.py:23 | OK |
| target3 | 3430ffa41b21d24b | api_signature | error | OK | API001/required_entity_signature_return/v1 | checkout:CheckoutService.checkout | checkout:CheckoutService.checkout | checkout.py:23 | OK |
| target3 | e699c682fa856e36 | api_signature | error | OK | API002/required_method/v1 | checkout:CheckoutService.checkout | checkout:CheckoutService.checkout | checkout.py:23 | OK |
| target3 | 1e3c754f6db6a13e | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Order | models:Order | models.py:66 | OK |
| target3 | 20d432893dc79adc | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Product | models:Product | models.py:18 | OK |
| target3 | b37dbd41b368ccd3 | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Order | models:Order | models.py:66 | OK |
| target3 | 62f5354cfb5fd32a | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Product | models:Product | models.py:18 | OK |
| target3 | 15cd25fa82be0834 | attribute_contract | error | OK | API003/required_attribute/v1/d2 | models:Order | models:Order | models.py:66 | OK |
| target3 | 33d722991538be0b | attribute_contract | error | OK | API003/required_attribute/v1/d2 | models:Product | models:Product | models.py:18 | OK |
| target3 | 98b9b5deff11ff55 | attribute_contract | error | OK | API003/required_attribute/v1/d3 | models:Order | models:Order | models.py:66 | OK |
| target3 | 203267e79b8a0848 | api_signature | error | OK | API003/required_constructor/v1 | models:Product | models:Product | models.py:18 | OK |
| target3 | 14c5cdfe3131ada5 | api_signature | error | OK | API004/required_factory/v1 | models:Cart.empty | models:Cart.empty | models.py:42 | OK |
| target3 | 8eb37c03d995b319 | api_signature | error | OK | API004/required_factory/v1 | models:Order.from_cart | models:Order.from_cart | models.py:90 | OK |
