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

## Matching Candidates (Debug)

Showing top 10 candidates per source object.

### Source: Cart

- Source: Cart [class] (source:source:models:Cart:class:-) @ models.py:41
- Match status: `matched`
- Selected match: Cart [class] (target:target5:models:Cart:class:-) @ models.py:13
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart [class] (target:target5:models:Cart:class:-) @ models.py:13 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: CheckoutService

- Source: CheckoutService [class] (source:source:checkout:CheckoutService:class:-) @ checkout.py:17
- Match status: `unmatched`
- Selected match: N/A
- Overall confidence: 0

Candidates (0/0):

No candidates recorded.

### Source: InMemoryOrderRepository

- Source: InMemoryOrderRepository [class] (source:source:storage.repository:InMemoryOrderRepository:class:-) @ storage/repository.py:16
- Match status: `unmatched`
- Selected match: N/A
- Overall confidence: 0

Candidates (0/0):

No candidates recorded.

### Source: Order

- Source: Order [class] (source:source:models:Order:class:-) @ models.py:72
- Match status: `matched`
- Selected match: Order [class] (target:target5:models:Order:class:-) @ models.py:34
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Order [class] (target:target5:models:Order:class:-) @ models.py:34 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Order | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: OrderRepository

- Source: OrderRepository [class] (source:source:contracts:OrderRepository:class:-) @ contracts.py:15
- Match status: `unmatched`
- Selected match: N/A
- Overall confidence: 0

Candidates (0/0):

No candidates recorded.

### Source: Product

- Source: Product [class] (source:source:models:Product:class:-) @ models.py:18
- Match status: `matched`
- Selected match: Product [class] (target:target5:models:Product:class:-) @ models.py:6
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Product [class] (target:target5:models:Product:class:-) @ models.py:6 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Product | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.__init__

- Source: Cart.__init__ [method] (source:source:models:Cart.__init__:method:p0-a2-v0-k0-w0-d1-kd0) @ models.py:44
- Match status: `matched`
- Selected match: Cart.__init__ [method] (target:target5:models:Cart.__init__:method:p0-a2-v0-k0-w0-d1-kd0) @ models.py:14
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.__init__ [method] (target:target5:models:Cart.__init__:method:p0-a2-v0-k0-w0-d1-kd0) @ models.py:14 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.__init__ | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.add_item

- Source: Cart.add_item [method] (source:source:models:Cart.add_item:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:59
- Match status: `matched`
- Selected match: Cart.add_item [method] (target:target5:models:Cart.add_item:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:21
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.add_item [method] (target:target5:models:Cart.add_item:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:21 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.add_item | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.empty

- Source: Cart.empty [method] (source:source:models:Cart.empty:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:48
- Match status: `matched`
- Selected match: Cart.empty [method] (target:target5:models:Cart.empty:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:18
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.empty [method] (target:target5:models:Cart.empty:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:18 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.empty | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.items

- Source: Cart.items [method] (source:source:models:Cart.items:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:68
- Match status: `matched`
- Selected match: Cart.items [method] (target:target5:models:Cart.items:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:30
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.items [method] (target:target5:models:Cart.items:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:30 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.items | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.remove_item

- Source: Cart.remove_item [method] (source:source:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:62
- Match status: `matched`
- Selected match: Cart.remove_item [method] (target:target5:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.remove_item [method] (target:target5:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.remove_item | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.total

- Source: Cart.total [method] (source:source:models:Cart.total:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:65
- Match status: `matched`
- Selected match: Cart.total [method] (target:target5:models:Cart.total:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:27
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.total [method] (target:target5:models:Cart.total:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:27 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.total | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: CheckoutService.__init__

- Source: CheckoutService.__init__ [method] (source:source:checkout:CheckoutService.__init__:method:p0-a2-v0-k0-w0-d0-kd0) @ checkout.py:20
- Match status: `unmatched`
- Selected match: Product.__init__ [method] (target:target5:models:Product.__init__:method:p0-a4-v0-k0-w0-d0-kd0) @ models.py:7
- Overall confidence: 0.2325

Candidates (4/4):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Product.__init__ [method] (target:target5:models:Product.__init__:method:p0-a4-v0-k0-w0-d0-kd0) @ models.py:7 | 0.2325 |  |
| 2 | Cart.__init__ [method] (target:target5:models:Cart.__init__:method:p0-a2-v0-k0-w0-d1-kd0) @ models.py:14 | 0.224516 |  |
| 3 | Order.__init__ [method] (target:target5:models:Order.__init__:method:p0-a5-v0-k0-w0-d0-kd0) @ models.py:35 | 0.197143 |  |
| 4 | Cart.remove_item [method] (target:target5:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24 | 0 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Product.__init__ | 0.2325 | 0.214286 | 0 | 1 | 0 | 0.15 | 0.333333 |
| Cart.__init__ | 0.224516 | 0.193548 | 0 | 1 | 0 | 0.15 | 0.333333 |
| Order.__init__ | 0.197143 | 0.122449 | 0 | 1 | 0 | 0.15 | 0.333333 |
| Cart.remove_item | 0 | 0.21875 | 0 | 0.181818 | 0 | 0.15 | 0.333333 |

### Source: CheckoutService.checkout

- Source: CheckoutService.checkout [method] (source:source:checkout:CheckoutService.checkout:method:p0-a3-v0-k0-w0-d0-kd0) @ checkout.py:23
- Match status: `unmatched`
- Selected match: Order.from_cart [method] (target:target5:models:Order.from_cart:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:48
- Overall confidence: 0.079929

Candidates (2/2):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Order.from_cart [method] (target:target5:models:Order.from_cart:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:48 | 0.079929 |  |
| 2 | Cart.add_item [method] (target:target5:models:Cart.add_item:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:21 | 0 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Order.from_cart | 0.079929 | 0.510638 | 0 | 0.111111 | 0 | 0.15 | 0.333333 |
| Cart.add_item | 0 | 0.325581 | 0 | 0 | 0 | 0.15 | 0.333333 |

### Source: InMemoryOrderRepository.__init__

- Source: InMemoryOrderRepository.__init__ [method] (source:source:storage.repository:InMemoryOrderRepository.__init__:method:p0-a1-v0-k0-w0-d0-kd0) @ storage/repository.py:28
- Match status: `unmatched`
- Selected match: Cart.__init__ [method] (target:target5:models:Cart.__init__:method:p0-a2-v0-k0-w0-d1-kd0) @ models.py:14
- Overall confidence: 0.33629

Candidates (5/5):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.__init__ [method] (target:target5:models:Cart.__init__:method:p0-a2-v0-k0-w0-d1-kd0) @ models.py:14 | 0.33629 |  |
| 2 | Product.__init__ [method] (target:target5:models:Product.__init__:method:p0-a4-v0-k0-w0-d0-kd0) @ models.py:7 | 0.316833 |  |
| 3 | Order.__init__ [method] (target:target5:models:Order.__init__:method:p0-a5-v0-k0-w0-d0-kd0) @ models.py:35 | 0.267857 |  |
| 4 | Cart.total [method] (target:target5:models:Cart.total:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:27 | 0.060086 |  |
| 5 | Cart.items [method] (target:target5:models:Cart.items:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:30 | 0.009079 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.__init__ | 0.33629 | 0.483871 | 0 | 1 | 0 | 0.15 | 0.25 |
| Product.__init__ | 0.316833 | 0.433333 | 0 | 1 | 0 | 0.15 | 0.25 |
| Order.__init__ | 0.267857 | 0.306122 | 0 | 1 | 0 | 0.15 | 0.25 |
| Cart.total | 0.060086 | 0.448276 | 0 | 0.125 | 0 | 0.15 | 0.25 |
| Cart.items | 0.009079 | 0.315789 | 0 | 0.125 | 0 | 0.15 | 0.25 |

### Source: InMemoryOrderRepository.get

- Source: InMemoryOrderRepository.get [method] (source:source:storage.repository:InMemoryOrderRepository.get:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:35
- Match status: `unmatched`
- Selected match: Cart.remove_item [method] (target:target5:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24
- Overall confidence: 0

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.remove_item [method] (target:target5:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24 | 0 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.remove_item | 0 | 0.205882 | 0 | 0.181818 | 0 | 0.15 | 0.25 |

### Source: InMemoryOrderRepository.save

- Source: InMemoryOrderRepository.save [method] (source:source:storage.repository:InMemoryOrderRepository.save:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:31
- Match status: `unmatched`
- Selected match: Cart.remove_item [method] (target:target5:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24
- Overall confidence: 0.063075

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.remove_item [method] (target:target5:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24 | 0.063075 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.remove_item | 0.063075 | 0.411765 | 0 | 0.181818 | 0 | 0.15 | 0.25 |

### Source: Order.__init__

- Source: Order.__init__ [method] (source:source:models:Order.__init__:method:p0-a5-v0-k0-w0-d0-kd0) @ models.py:92
- Match status: `matched`
- Selected match: Order.__init__ [method] (target:target5:models:Order.__init__:method:p0-a5-v0-k0-w0-d0-kd0) @ models.py:35
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Order.__init__ [method] (target:target5:models:Order.__init__:method:p0-a5-v0-k0-w0-d0-kd0) @ models.py:35 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Order.__init__ | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Order.from_cart

- Source: Order.from_cart [method] (source:source:models:Order.from_cart:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:105
- Match status: `matched`
- Selected match: Order.from_cart [method] (target:target5:models:Order.from_cart:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:48
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Order.from_cart [method] (target:target5:models:Order.from_cart:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:48 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Order.from_cart | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: OrderRepository.get

- Source: OrderRepository.get [method] (source:source:contracts:OrderRepository.get:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:21
- Match status: `unmatched`
- Selected match: Cart.remove_item [method] (target:target5:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24
- Overall confidence: 0

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.remove_item [method] (target:target5:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24 | 0 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.remove_item | 0 | 0 | 0 | 0.181818 | 0 | 0.15 | 0.333333 |

### Source: OrderRepository.save

- Source: OrderRepository.save [method] (source:source:contracts:OrderRepository.save:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:18
- Match status: `unmatched`
- Selected match: Cart.remove_item [method] (target:target5:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24
- Overall confidence: 0

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.remove_item [method] (target:target5:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24 | 0 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.remove_item | 0 | 0 | 0 | 0.181818 | 0 | 0.15 | 0.333333 |

### Source: Product.__init__

- Source: Product.__init__ [method] (source:source:models:Product.__init__:method:p0-a4-v0-k0-w0-d0-kd0) @ models.py:35
- Match status: `matched`
- Selected match: Product.__init__ [method] (target:target5:models:Product.__init__:method:p0-a4-v0-k0-w0-d0-kd0) @ models.py:7
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Product.__init__ [method] (target:target5:models:Product.__init__:method:p0-a4-v0-k0-w0-d0-kd0) @ models.py:7 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Product.__init__ | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: __init__

- Source: __init__ [module] (source:source:::module:-) @ __init__.py:1
- Match status: `matched`
- Selected match: __init__ [module] (target:target5:::module:-) @ __init__.py:1
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | __init__ [module] (target:target5:::module:-) @ __init__.py:1 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| __init__ | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: checkout

- Source: checkout [module] (source:source:checkout:checkout:module:-) @ checkout.py:1
- Match status: `unmatched`
- Selected match: N/A
- Overall confidence: 0

Candidates (0/0):

No candidates recorded.

### Source: contracts

- Source: contracts [module] (source:source:contracts:contracts:module:-) @ contracts.py:1
- Match status: `unmatched`
- Selected match: N/A
- Overall confidence: 0

Candidates (0/0):

No candidates recorded.

### Source: models

- Source: models [module] (source:source:models:models:module:-) @ models.py:1
- Match status: `matched`
- Selected match: models [module] (target:target5:models:models:module:-) @ models.py:1
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | models [module] (target:target5:models:models:module:-) @ models.py:1 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| models | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: storage

- Source: storage [module] (source:source:storage:storage:module:-) @ storage/__init__.py:1
- Match status: `unmatched`
- Selected match: N/A
- Overall confidence: 0

Candidates (0/0):

No candidates recorded.

### Source: storage.repository

- Source: storage.repository [module] (source:source:storage.repository:storage.repository:module:-) @ storage/repository.py:1
- Match status: `unmatched`
- Selected match: N/A
- Overall confidence: 0

Candidates (0/0):

No candidates recorded.

## Results

| Project | Result ID | Category | Severity | Status | Rule | Source | Target | Location | Message |
|---|---|---|---|---|---|---|---|---|---|
| target5 | 617ac00a309f1335 | api_signature | error | FAILED | API001/required_entity_signature/v1 | checkout:CheckoutService.checkout |  | checkout.py:23 | Required target entity missing or not matchable (status=unmatched, confidence=0.079929). |
| target5 | 643d2ef7732dbbe0 | api_signature | error | FAILED | API002/required_method/v1 | checkout:CheckoutService.checkout |  | checkout.py:23 | Required target entity missing or not matchable (status=unmatched, confidence=0.079929). |
| target5 | 61b8c934384c7c3f | protocol_conformance | error | FAILED | PRO001/implements_protocol/v1 | storage.repository:InMemoryOrderRepository |  | storage/repository.py:16 | Required target entity missing or not matchable (status=unmatched, confidence=0.0). |
| target5 | 947469e3141dd17a | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Order | models:Order | models.py:72 | OK |
| target5 | b7f7200143a8744b | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Product | models:Product | models.py:18 | OK |
| target5 | 02c7be940933c9ca | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Order | models:Order | models.py:72 | OK |
| target5 | d0b241e748099f5e | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Product | models:Product | models.py:18 | OK |
| target5 | 8c5d97c9a7498ac2 | attribute_contract | error | OK | API003/required_attribute/v1/d2 | models:Order | models:Order | models.py:72 | OK |
| target5 | 86e1ac0ef0547c0b | attribute_contract | error | OK | API003/required_attribute/v1/d2 | models:Product | models:Product | models.py:18 | OK |
| target5 | f4b2aff71ddc7605 | attribute_contract | error | OK | API003/required_attribute/v1/d3 | models:Order | models:Order | models.py:72 | OK |
| target5 | c68ad207f8e7dce4 | api_signature | error | OK | API003/required_constructor/v1 | models:Product | models:Product | models.py:18 | OK |
| target5 | 3c1f5b6096452650 | api_signature | error | OK | API004/required_factory/v1 | models:Cart.empty | models:Cart.empty | models.py:48 | OK |
| target5 | bdbe910f309c7365 | api_signature | error | OK | API004/required_factory/v1 | models:Order.from_cart | models:Order.from_cart | models.py:105 | OK |
| target5 | 6331e497e8ac915b | import_policy | error | OK | DEP001/forbid_imports/v2 | storage:storage |  | storage/__init__.py:1 | OK |
| target5 | e534fb1addda3354 | api_signature | warning | SKIPPED | API001/required_entity_signature_return/v1 | checkout:CheckoutService.checkout |  | checkout.py:23 | Rule skipped due to matching status unmatched (confidence=0.079929). |
