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

## Matching Candidates (Debug)

Showing top 10 candidates per source object.

### Source: Cart

- Source: Cart [class] (source:source:models:Cart:class:-) @ models.py:41
- Match status: `matched`
- Selected match: Cart [class] (target:target2:models:Cart:class:-) @ models.py:19
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart [class] (target:target2:models:Cart:class:-) @ models.py:19 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: CheckoutService

- Source: CheckoutService [class] (source:source:checkout:CheckoutService:class:-) @ checkout.py:17
- Match status: `matched`
- Selected match: CheckoutService [class] (target:target2:checkout:CheckoutService:class:-) @ checkout.py:12
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | CheckoutService [class] (target:target2:checkout:CheckoutService:class:-) @ checkout.py:12 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| CheckoutService | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: InMemoryOrderRepository

- Source: InMemoryOrderRepository [class] (source:source:storage.repository:InMemoryOrderRepository:class:-) @ storage/repository.py:16
- Match status: `matched`
- Selected match: InMemoryOrderRepository [class] (target:target2:storage.repository:InMemoryOrderRepository:class:-) @ storage/repository.py:8
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | InMemoryOrderRepository [class] (target:target2:storage.repository:InMemoryOrderRepository:class:-) @ storage/repository.py:8 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| InMemoryOrderRepository | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Order

- Source: Order [class] (source:source:models:Order:class:-) @ models.py:72
- Match status: `matched`
- Selected match: Order [class] (target:target2:models:Order:class:-) @ models.py:40
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Order [class] (target:target2:models:Order:class:-) @ models.py:40 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Order | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: OrderRepository

- Source: OrderRepository [class] (source:source:contracts:OrderRepository:class:-) @ contracts.py:15
- Match status: `matched`
- Selected match: OrderRepository [class] (target:target2:contracts:OrderRepository:class:-) @ contracts.py:11
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | OrderRepository [class] (target:target2:contracts:OrderRepository:class:-) @ contracts.py:11 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| OrderRepository | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Product

- Source: Product [class] (source:source:models:Product:class:-) @ models.py:18
- Match status: `matched`
- Selected match: Product [class] (target:target2:models:Product:class:-) @ models.py:12
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Product [class] (target:target2:models:Product:class:-) @ models.py:12 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Product | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.__init__

- Source: Cart.__init__ [method] (source:source:models:Cart.__init__:method:p0-a2-v0-k0-w0-d1-kd0) @ models.py:44
- Match status: `matched`
- Selected match: Cart.__init__ [method] (target:target2:models:Cart.__init__:method:p0-a2-v0-k0-w0-d1-kd0) @ models.py:20
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.__init__ [method] (target:target2:models:Cart.__init__:method:p0-a2-v0-k0-w0-d1-kd0) @ models.py:20 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.__init__ | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.add_item

- Source: Cart.add_item [method] (source:source:models:Cart.add_item:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:59
- Match status: `matched`
- Selected match: Cart.add_item [method] (target:target2:models:Cart.add_item:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:27
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.add_item [method] (target:target2:models:Cart.add_item:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:27 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.add_item | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.empty

- Source: Cart.empty [method] (source:source:models:Cart.empty:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:48
- Match status: `matched`
- Selected match: Cart.empty [method] (target:target2:models:Cart.empty:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:24
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.empty [method] (target:target2:models:Cart.empty:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:24 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.empty | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.items

- Source: Cart.items [method] (source:source:models:Cart.items:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:68
- Match status: `matched`
- Selected match: Cart.items [method] (target:target2:models:Cart.items:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:36
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.items [method] (target:target2:models:Cart.items:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:36 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.items | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.remove_item

- Source: Cart.remove_item [method] (source:source:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:62
- Match status: `matched`
- Selected match: Cart.remove_item [method] (target:target2:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:30
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.remove_item [method] (target:target2:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:30 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.remove_item | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.total

- Source: Cart.total [method] (source:source:models:Cart.total:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:65
- Match status: `matched`
- Selected match: Cart.total [method] (target:target2:models:Cart.total:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:33
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.total [method] (target:target2:models:Cart.total:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:33 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.total | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: CheckoutService.__init__

- Source: CheckoutService.__init__ [method] (source:source:checkout:CheckoutService.__init__:method:p0-a2-v0-k0-w0-d0-kd0) @ checkout.py:20
- Match status: `matched`
- Selected match: CheckoutService.__init__ [method] (target:target2:checkout:CheckoutService.__init__:method:p0-a2-v0-k0-w0-d0-kd0) @ checkout.py:13
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | CheckoutService.__init__ [method] (target:target2:checkout:CheckoutService.__init__:method:p0-a2-v0-k0-w0-d0-kd0) @ checkout.py:13 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| CheckoutService.__init__ | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: CheckoutService.checkout

- Source: CheckoutService.checkout [method] (source:source:checkout:CheckoutService.checkout:method:p0-a3-v0-k0-w0-d0-kd0) @ checkout.py:23
- Match status: `matched`
- Selected match: CheckoutService.checkout [method] (target:target2:checkout:CheckoutService.checkout:method:p0-a3-v0-k0-w0-d0-kd0) @ checkout.py:16
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | CheckoutService.checkout [method] (target:target2:checkout:CheckoutService.checkout:method:p0-a3-v0-k0-w0-d0-kd0) @ checkout.py:16 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| CheckoutService.checkout | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: InMemoryOrderRepository.__init__

- Source: InMemoryOrderRepository.__init__ [method] (source:source:storage.repository:InMemoryOrderRepository.__init__:method:p0-a1-v0-k0-w0-d0-kd0) @ storage/repository.py:28
- Match status: `matched`
- Selected match: InMemoryOrderRepository.__init__ [method] (target:target2:storage.repository:InMemoryOrderRepository.__init__:method:p0-a1-v0-k0-w0-d0-kd0) @ storage/repository.py:9
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | InMemoryOrderRepository.__init__ [method] (target:target2:storage.repository:InMemoryOrderRepository.__init__:method:p0-a1-v0-k0-w0-d0-kd0) @ storage/repository.py:9 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| InMemoryOrderRepository.__init__ | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: InMemoryOrderRepository.get

- Source: InMemoryOrderRepository.get [method] (source:source:storage.repository:InMemoryOrderRepository.get:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:35
- Match status: `matched`
- Selected match: InMemoryOrderRepository.get [method] (target:target2:storage.repository:InMemoryOrderRepository.get:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:16
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | InMemoryOrderRepository.get [method] (target:target2:storage.repository:InMemoryOrderRepository.get:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:16 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| InMemoryOrderRepository.get | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: InMemoryOrderRepository.save

- Source: InMemoryOrderRepository.save [method] (source:source:storage.repository:InMemoryOrderRepository.save:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:31
- Match status: `matched`
- Selected match: InMemoryOrderRepository.save [method] (target:target2:storage.repository:InMemoryOrderRepository.save:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:12
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | InMemoryOrderRepository.save [method] (target:target2:storage.repository:InMemoryOrderRepository.save:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:12 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| InMemoryOrderRepository.save | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Order.__init__

- Source: Order.__init__ [method] (source:source:models:Order.__init__:method:p0-a5-v0-k0-w0-d0-kd0) @ models.py:92
- Match status: `low_confidence`
- Selected match: Order.__init__ [method] (target:target2:models:Order.__init__:method:p0-a4-v0-k0-w0-d0-kd0) @ models.py:41
- Overall confidence: 0.747812

Candidates (5/5):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Order.__init__ [method] (target:target2:models:Order.__init__:method:p0-a4-v0-k0-w0-d0-kd0) @ models.py:41 | 0.747812 |  |
| 2 | Cart.__init__ [method] (target:target2:models:Cart.__init__:method:p0-a2-v0-k0-w0-d1-kd0) @ models.py:20 | 0.6075 |  |
| 3 | Product.__init__ [method] (target:target2:models:Product.__init__:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:13 | 0.6075 |  |
| 4 | InMemoryOrderRepository.__init__ [method] (target:target2:storage.repository:InMemoryOrderRepository.__init__:method:p0-a1-v0-k0-w0-d0-kd0) @ storage/repository.py:9 | 0.267857 |  |
| 5 | CheckoutService.__init__ [method] (target:target2:checkout:CheckoutService.__init__:method:p0-a2-v0-k0-w0-d0-kd0) @ checkout.py:13 | 0.197143 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Order.__init__ | 0.747812 | 0.8125 | 1 | 1 | 0 | 0.03 | 1 |
| Cart.__init__ | 0.6075 | 0.5 | 1 | 1 | 0 | 0.05 | 1 |
| Product.__init__ | 0.6075 | 0.5 | 1 | 1 | 0 | 0.05 | 1 |
| InMemoryOrderRepository.__init__ | 0.267857 | 0.306122 | 0 | 1 | 0 | 0.15 | 0.25 |
| CheckoutService.__init__ | 0.197143 | 0.122449 | 0 | 1 | 0 | 0.15 | 0.333333 |

### Source: Order.from_cart

- Source: Order.from_cart [method] (source:source:models:Order.from_cart:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:105
- Match status: `matched`
- Selected match: Order.from_cart [method] (target:target2:models:Order.from_cart:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:52
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Order.from_cart [method] (target:target2:models:Order.from_cart:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:52 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Order.from_cart | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: OrderRepository.get

- Source: OrderRepository.get [method] (source:source:contracts:OrderRepository.get:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:21
- Match status: `matched`
- Selected match: OrderRepository.get [method] (target:target2:contracts:OrderRepository.get:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:13
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | OrderRepository.get [method] (target:target2:contracts:OrderRepository.get:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:13 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| OrderRepository.get | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: OrderRepository.save

- Source: OrderRepository.save [method] (source:source:contracts:OrderRepository.save:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:18
- Match status: `matched`
- Selected match: OrderRepository.save [method] (target:target2:contracts:OrderRepository.save:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:12
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | OrderRepository.save [method] (target:target2:contracts:OrderRepository.save:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:12 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| OrderRepository.save | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Product.__init__

- Source: Product.__init__ [method] (source:source:models:Product.__init__:method:p0-a4-v0-k0-w0-d0-kd0) @ models.py:35
- Match status: `low_confidence`
- Selected match: Order.__init__ [method] (target:target2:models:Order.__init__:method:p0-a4-v0-k0-w0-d0-kd0) @ models.py:41
- Overall confidence: 0.784615

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Order.__init__ [method] (target:target2:models:Order.__init__:method:p0-a4-v0-k0-w0-d0-kd0) @ models.py:41 | 0.784615 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Order.__init__ | 0.784615 | 0.692308 | 1 | 1 | 0 | 0 | 1 |

### Source: __init__

- Source: __init__ [module] (source:source:::module:-) @ __init__.py:1
- Match status: `matched`
- Selected match: __init__ [module] (target:target2:::module:-) @ __init__.py:1
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | __init__ [module] (target:target2:::module:-) @ __init__.py:1 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| __init__ | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: checkout

- Source: checkout [module] (source:source:checkout:checkout:module:-) @ checkout.py:1
- Match status: `matched`
- Selected match: checkout [module] (target:target2:checkout:checkout:module:-) @ checkout.py:1
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | checkout [module] (target:target2:checkout:checkout:module:-) @ checkout.py:1 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| checkout | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: contracts

- Source: contracts [module] (source:source:contracts:contracts:module:-) @ contracts.py:1
- Match status: `matched`
- Selected match: contracts [module] (target:target2:contracts:contracts:module:-) @ contracts.py:1
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | contracts [module] (target:target2:contracts:contracts:module:-) @ contracts.py:1 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| contracts | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: models

- Source: models [module] (source:source:models:models:module:-) @ models.py:1
- Match status: `matched`
- Selected match: models [module] (target:target2:models:models:module:-) @ models.py:1
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | models [module] (target:target2:models:models:module:-) @ models.py:1 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| models | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: storage

- Source: storage [module] (source:source:storage:storage:module:-) @ storage/__init__.py:1
- Match status: `matched`
- Selected match: storage [module] (target:target2:storage:storage:module:-) @ storage/__init__.py:1
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | storage [module] (target:target2:storage:storage:module:-) @ storage/__init__.py:1 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| storage | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: storage.repository

- Source: storage.repository [module] (source:source:storage.repository:storage.repository:module:-) @ storage/repository.py:1
- Match status: `matched`
- Selected match: storage.repository [module] (target:target2:storage.repository:storage.repository:module:-) @ storage/repository.py:1
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | storage.repository [module] (target:target2:storage.repository:storage.repository:module:-) @ storage/repository.py:1 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| storage.repository | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

## Results

| Project | Result ID | Category | Severity | Status | Rule | Source | Target | Location | Message |
|---|---|---|---|---|---|---|---|---|---|
| target2 | dcd965061fa9beeb | api_signature | error | FAILED | API001/required_entity_signature_return/v1 | checkout:CheckoutService.checkout | checkout:CheckoutService.checkout | checkout.py:23 | Required return annotation mismatch for checkout:CheckoutService.checkout: return annotation mismatch: expected models.Order, found dict |
| target2 | fe0aedd0dc2e6774 | attribute_contract | error | FAILED | API003/required_attribute/v1/d2 | models:Order | models:Order | models.py:72 | Required attribute mismatch for models:Order: missing required attribute 'total' |
| target2 | 88a4a6ad82693a2e | api_signature | error | FAILED | API003/required_constructor/v1 | models:Product | models:Product | models.py:18 | Required constructor mismatch for models:Product: missing parameter 'sku' |
| target2 | 34d70e474167e7d2 | api_signature | error | OK | API001/required_entity_signature/v1 | checkout:CheckoutService.checkout | checkout:CheckoutService.checkout | checkout.py:23 | OK |
| target2 | 10a4e0b17d41aaa5 | api_signature | error | OK | API002/required_method/v1 | checkout:CheckoutService.checkout | checkout:CheckoutService.checkout | checkout.py:23 | OK |
| target2 | 1adad4cad33885b7 | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Order | models:Order | models.py:72 | OK |
| target2 | 0cf7a1b8fd943d5c | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Product | models:Product | models.py:18 | OK |
| target2 | aaf6ae9e5021f2f1 | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Order | models:Order | models.py:72 | OK |
| target2 | 4de38126a52ef921 | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Product | models:Product | models.py:18 | OK |
| target2 | 922759ecc9612dd6 | attribute_contract | error | OK | API003/required_attribute/v1/d2 | models:Product | models:Product | models.py:18 | OK |
| target2 | e2bcd96b8421e165 | attribute_contract | error | OK | API003/required_attribute/v1/d3 | models:Order | models:Order | models.py:72 | OK |
| target2 | 8ba93f01b4001339 | api_signature | error | OK | API004/required_factory/v1 | models:Cart.empty | models:Cart.empty | models.py:48 | OK |
| target2 | 632e560a50b3bc68 | api_signature | error | OK | API004/required_factory/v1 | models:Order.from_cart | models:Order.from_cart | models.py:105 | OK |
| target2 | 102a342684c3edff | import_policy | error | OK | DEP001/forbid_imports/v2 | storage:storage | storage:storage | storage/__init__.py:1 | OK |
| target2 | cdc7dc46ae9a2bdb | protocol_conformance | error | OK | PRO001/implements_protocol/v1 | storage.repository:InMemoryOrderRepository | storage.repository:InMemoryOrderRepository | storage/repository.py:16 | OK |
