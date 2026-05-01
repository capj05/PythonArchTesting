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

## Matching Candidates (Debug)

Showing top 10 candidates per source object.

### Source: Cart

- Source: Cart [class] (source:source:models:Cart:class:-) @ models.py:41
- Match status: `matched`
- Selected match: Cart [class] (target:target4:models:Cart:class:-) @ models.py:13
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart [class] (target:target4:models:Cart:class:-) @ models.py:13 | 1 |  |

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
- Selected match: Order [class] (target:target4:models:Order:class:-) @ models.py:34
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Order [class] (target:target4:models:Order:class:-) @ models.py:34 | 1 |  |

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
- Selected match: Product [class] (target:target4:models:Product:class:-) @ models.py:6
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Product [class] (target:target4:models:Product:class:-) @ models.py:6 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Product | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.__init__

- Source: Cart.__init__ [method] (source:source:models:Cart.__init__:method:p0-a2-v0-k0-w0-d1-kd0) @ models.py:44
- Match status: `matched`
- Selected match: Cart.__init__ [method] (target:target4:models:Cart.__init__:method:p0-a2-v0-k0-w0-d1-kd0) @ models.py:14
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.__init__ [method] (target:target4:models:Cart.__init__:method:p0-a2-v0-k0-w0-d1-kd0) @ models.py:14 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.__init__ | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.add_item

- Source: Cart.add_item [method] (source:source:models:Cart.add_item:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:59
- Match status: `matched`
- Selected match: Cart.add_item [method] (target:target4:models:Cart.add_item:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:21
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.add_item [method] (target:target4:models:Cart.add_item:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:21 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.add_item | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.empty

- Source: Cart.empty [method] (source:source:models:Cart.empty:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:48
- Match status: `matched`
- Selected match: Cart.empty [method] (target:target4:models:Cart.empty:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:18
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.empty [method] (target:target4:models:Cart.empty:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:18 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.empty | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.items

- Source: Cart.items [method] (source:source:models:Cart.items:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:68
- Match status: `matched`
- Selected match: Cart.items [method] (target:target4:models:Cart.items:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:30
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.items [method] (target:target4:models:Cart.items:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:30 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.items | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.remove_item

- Source: Cart.remove_item [method] (source:source:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:62
- Match status: `matched`
- Selected match: Cart.remove_item [method] (target:target4:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.remove_item [method] (target:target4:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.remove_item | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Cart.total

- Source: Cart.total [method] (source:source:models:Cart.total:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:65
- Match status: `matched`
- Selected match: Cart.total [method] (target:target4:models:Cart.total:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:27
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Cart.total [method] (target:target4:models:Cart.total:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:27 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Cart.total | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: CheckoutService.__init__

- Source: CheckoutService.__init__ [method] (source:source:checkout:CheckoutService.__init__:method:p0-a2-v0-k0-w0-d0-kd0) @ checkout.py:20
- Match status: `matched`
- Selected match: Checkout.__init__ [method] (target:target4:checkout:Checkout.__init__:method:p0-a2-v0-k0-w0-d0-kd0) @ checkout.py:15
- Overall confidence: 1

Candidates (5/5):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Checkout.__init__ [method] (target:target4:checkout:Checkout.__init__:method:p0-a2-v0-k0-w0-d0-kd0) @ checkout.py:15 | 1 |  |
| 2 | InMemoryStore.get [method] (target:target4:storage.repository:InMemoryStore.get:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:16 | 0.318182 |  |
| 3 | InMemoryStore.save [method] (target:target4:storage.repository:InMemoryStore.save:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:12 | 0.30625 |  |
| 4 | Cart.remove_item [method] (target:target4:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24 | 0.153125 |  |
| 5 | IOrderStore.get [method] (target:target4:contracts:IOrderStore.get:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:17 | 0 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Checkout.__init__ | 1 | 1 | 1 | 1 | 0 | 0 | 1 |
| InMemoryStore.get | 0.318182 | 0.454545 | 0 | 0.125 | 0 | 0 | 0.25 |
| InMemoryStore.save | 0.30625 | 0.4375 | 0 | 0 | 0 | 0 | 0.25 |
| Cart.remove_item | 0.153125 | 0.21875 | 0 | 0.181818 | 0 | 0 | 0.333333 |
| IOrderStore.get | 0 | 0 | 0 | 0.125 | 0 | 0 | 0.333333 |

### Source: CheckoutService.checkout

- Source: CheckoutService.checkout [method] (source:source:checkout:CheckoutService.checkout:method:p0-a3-v0-k0-w0-d0-kd0) @ checkout.py:23
- Match status: `low_confidence`
- Selected match: Checkout.process [method] (target:target4:checkout:Checkout.process:method:p0-a3-v0-k0-w0-d0-kd0) @ checkout.py:18
- Overall confidence: 0.7

Candidates (3/3):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Checkout.process [method] (target:target4:checkout:Checkout.process:method:p0-a3-v0-k0-w0-d0-kd0) @ checkout.py:18 | 0.7 |  |
| 2 | Order.from_cart [method] (target:target4:models:Order.from_cart:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:48 | 0.357447 |  |
| 3 | Cart.add_item [method] (target:target4:models:Cart.add_item:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:21 | 0.227907 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Checkout.process | 0.7 | 0.571429 | 1 | 0.125 | 0 | 0 | 1 |
| Order.from_cart | 0.357447 | 0.510638 | 0 | 0.111111 | 0 | 0 | 0.333333 |
| Cart.add_item | 0.227907 | 0.325581 | 0 | 0 | 0 | 0 | 0.333333 |

### Source: InMemoryOrderRepository.__init__

- Source: InMemoryOrderRepository.__init__ [method] (source:source:storage.repository:InMemoryOrderRepository.__init__:method:p0-a1-v0-k0-w0-d0-kd0) @ storage/repository.py:28
- Match status: `matched`
- Selected match: InMemoryStore.__init__ [method] (target:target4:storage.repository:InMemoryStore.__init__:method:p0-a1-v0-k0-w0-d0-kd0) @ storage/repository.py:9
- Overall confidence: 1

Candidates (4/4):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | InMemoryStore.__init__ [method] (target:target4:storage.repository:InMemoryStore.__init__:method:p0-a1-v0-k0-w0-d0-kd0) @ storage/repository.py:9 | 1 |  |
| 2 | Cart.total [method] (target:target4:models:Cart.total:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:27 | 0.313793 |  |
| 3 | Cart.items [method] (target:target4:models:Cart.items:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:30 | 0.221053 |  |
| 4 | Cart.empty [method] (target:target4:models:Cart.empty:method:p0-a1-v0-k0-w0-d0-kd0) @ models.py:18 | 0.073684 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| InMemoryStore.__init__ | 1 | 1 | 1 | 1 | 0 | 0 | 1 |
| Cart.total | 0.313793 | 0.448276 | 0 | 0.125 | 0 | 0 | 0.25 |
| Cart.items | 0.221053 | 0.315789 | 0 | 0.125 | 0 | 0 | 0.25 |
| Cart.empty | 0.073684 | 0.105263 | 0 | 0.125 | 0 | 0 | 0.25 |

### Source: InMemoryOrderRepository.get

- Source: InMemoryOrderRepository.get [method] (source:source:storage.repository:InMemoryOrderRepository.get:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:35
- Match status: `matched`
- Selected match: InMemoryStore.get [method] (target:target4:storage.repository:InMemoryStore.get:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:16
- Overall confidence: 1

Candidates (5/5):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | InMemoryStore.get [method] (target:target4:storage.repository:InMemoryStore.get:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:16 | 1 |  |
| 2 | InMemoryStore.save [method] (target:target4:storage.repository:InMemoryStore.save:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:12 | 0.69375 |  |
| 3 | Checkout.__init__ [method] (target:target4:checkout:Checkout.__init__:method:p0-a2-v0-k0-w0-d0-kd0) @ checkout.py:15 | 0.318182 |  |
| 4 | Cart.remove_item [method] (target:target4:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24 | 0.144118 |  |
| 5 | IOrderStore.get [method] (target:target4:contracts:IOrderStore.get:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:17 | 0 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| InMemoryStore.get | 1 | 1 | 1 | 1 | 0 | 0 | 1 |
| InMemoryStore.save | 0.69375 | 0.5625 | 1 | 0 | 0 | 0 | 1 |
| Checkout.__init__ | 0.318182 | 0.454545 | 0 | 0.125 | 0 | 0 | 0.25 |
| Cart.remove_item | 0.144118 | 0.205882 | 0 | 0.181818 | 0 | 0 | 0.25 |
| IOrderStore.get | 0 | 0 | 0 | 1 | 0 | 0 | 0.25 |

### Source: InMemoryOrderRepository.save

- Source: InMemoryOrderRepository.save [method] (source:source:storage.repository:InMemoryOrderRepository.save:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:31
- Match status: `matched`
- Selected match: InMemoryStore.save [method] (target:target4:storage.repository:InMemoryStore.save:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:12
- Overall confidence: 1

Candidates (5/5):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | InMemoryStore.save [method] (target:target4:storage.repository:InMemoryStore.save:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:12 | 1 |  |
| 2 | InMemoryStore.get [method] (target:target4:storage.repository:InMemoryStore.get:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:16 | 0.69375 |  |
| 3 | Checkout.__init__ [method] (target:target4:checkout:Checkout.__init__:method:p0-a2-v0-k0-w0-d0-kd0) @ checkout.py:15 | 0.30625 |  |
| 4 | Cart.remove_item [method] (target:target4:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24 | 0.288235 |  |
| 5 | IOrderStore.get [method] (target:target4:contracts:IOrderStore.get:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:17 | 0 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| InMemoryStore.save | 1 | 1 | 1 | 1 | 0 | 0 | 1 |
| InMemoryStore.get | 0.69375 | 0.5625 | 1 | 0 | 0 | 0 | 1 |
| Checkout.__init__ | 0.30625 | 0.4375 | 0 | 0 | 0 | 0 | 0.25 |
| Cart.remove_item | 0.288235 | 0.411765 | 0 | 0.181818 | 0 | 0 | 0.25 |
| IOrderStore.get | 0 | 0 | 0 | 0 | 0 | 0 | 0.25 |

### Source: Order.__init__

- Source: Order.__init__ [method] (source:source:models:Order.__init__:method:p0-a5-v0-k0-w0-d0-kd0) @ models.py:92
- Match status: `matched`
- Selected match: Order.__init__ [method] (target:target4:models:Order.__init__:method:p0-a5-v0-k0-w0-d0-kd0) @ models.py:35
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Order.__init__ [method] (target:target4:models:Order.__init__:method:p0-a5-v0-k0-w0-d0-kd0) @ models.py:35 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Order.__init__ | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: Order.from_cart

- Source: Order.from_cart [method] (source:source:models:Order.from_cart:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:105
- Match status: `matched`
- Selected match: Order.from_cart [method] (target:target4:models:Order.from_cart:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:48
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Order.from_cart [method] (target:target4:models:Order.from_cart:method:p0-a3-v0-k0-w0-d0-kd0) @ models.py:48 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Order.from_cart | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: OrderRepository.get

- Source: OrderRepository.get [method] (source:source:contracts:OrderRepository.get:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:21
- Match status: `low_confidence`
- Selected match: IOrderStore.get [method] (target:target4:contracts:IOrderStore.get:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:17
- Overall confidence: 0.65

Candidates (5/5):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | IOrderStore.get [method] (target:target4:contracts:IOrderStore.get:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:17 | 0.65 |  |
| 2 | IOrderStore.save [method] (target:target4:contracts:IOrderStore.save:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:16 | 0.65 |  |
| 3 | Checkout.__init__ [method] (target:target4:checkout:Checkout.__init__:method:p0-a2-v0-k0-w0-d0-kd0) @ checkout.py:15 | 0 |  |
| 4 | Cart.remove_item [method] (target:target4:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24 | 0 |  |
| 5 | InMemoryStore.get [method] (target:target4:storage.repository:InMemoryStore.get:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:16 | 0 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| IOrderStore.get | 0.65 | 0.5 | 1 | 1 | 0 | 0 | 1 |
| IOrderStore.save | 0.65 | 0.5 | 1 | 0 | 0 | 0 | 1 |
| Checkout.__init__ | 0 | 0 | 0 | 0.125 | 0 | 0 | 0.333333 |
| Cart.remove_item | 0 | 0 | 0 | 0.181818 | 0 | 0 | 0.333333 |
| InMemoryStore.get | 0 | 0 | 0 | 1 | 0 | 0 | 0.25 |

### Source: OrderRepository.save

- Source: OrderRepository.save [method] (source:source:contracts:OrderRepository.save:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:18
- Match status: `low_confidence`
- Selected match: IOrderStore.get [method] (target:target4:contracts:IOrderStore.get:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:17
- Overall confidence: 0.65

Candidates (5/5):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | IOrderStore.get [method] (target:target4:contracts:IOrderStore.get:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:17 | 0.65 |  |
| 2 | IOrderStore.save [method] (target:target4:contracts:IOrderStore.save:method:p0-a2-v0-k0-w0-d0-kd0) @ contracts.py:16 | 0.65 |  |
| 3 | Checkout.__init__ [method] (target:target4:checkout:Checkout.__init__:method:p0-a2-v0-k0-w0-d0-kd0) @ checkout.py:15 | 0 |  |
| 4 | Cart.remove_item [method] (target:target4:models:Cart.remove_item:method:p0-a2-v0-k0-w0-d0-kd0) @ models.py:24 | 0 |  |
| 5 | InMemoryStore.get [method] (target:target4:storage.repository:InMemoryStore.get:method:p0-a2-v0-k0-w0-d0-kd0) @ storage/repository.py:16 | 0 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| IOrderStore.get | 0.65 | 0.5 | 1 | 0 | 0 | 0 | 1 |
| IOrderStore.save | 0.65 | 0.5 | 1 | 1 | 0 | 0 | 1 |
| Checkout.__init__ | 0 | 0 | 0 | 0 | 0 | 0 | 0.333333 |
| Cart.remove_item | 0 | 0 | 0 | 0.181818 | 0 | 0 | 0.333333 |
| InMemoryStore.get | 0 | 0 | 0 | 0 | 0 | 0 | 0.25 |

### Source: Product.__init__

- Source: Product.__init__ [method] (source:source:models:Product.__init__:method:p0-a4-v0-k0-w0-d0-kd0) @ models.py:35
- Match status: `matched`
- Selected match: Product.__init__ [method] (target:target4:models:Product.__init__:method:p0-a4-v0-k0-w0-d0-kd0) @ models.py:7
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | Product.__init__ [method] (target:target4:models:Product.__init__:method:p0-a4-v0-k0-w0-d0-kd0) @ models.py:7 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| Product.__init__ | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: __init__

- Source: __init__ [module] (source:source:::module:-) @ __init__.py:1
- Match status: `matched`
- Selected match: __init__ [module] (target:target4:::module:-) @ __init__.py:1
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | __init__ [module] (target:target4:::module:-) @ __init__.py:1 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| __init__ | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: checkout

- Source: checkout [module] (source:source:checkout:checkout:module:-) @ checkout.py:1
- Match status: `matched`
- Selected match: checkout [module] (target:target4:checkout:checkout:module:-) @ checkout.py:1
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | checkout [module] (target:target4:checkout:checkout:module:-) @ checkout.py:1 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| checkout | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: contracts

- Source: contracts [module] (source:source:contracts:contracts:module:-) @ contracts.py:1
- Match status: `matched`
- Selected match: contracts [module] (target:target4:contracts:contracts:module:-) @ contracts.py:1
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | contracts [module] (target:target4:contracts:contracts:module:-) @ contracts.py:1 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| contracts | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: models

- Source: models [module] (source:source:models:models:module:-) @ models.py:1
- Match status: `matched`
- Selected match: models [module] (target:target4:models:models:module:-) @ models.py:1
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | models [module] (target:target4:models:models:module:-) @ models.py:1 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| models | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: storage

- Source: storage [module] (source:source:storage:storage:module:-) @ storage/__init__.py:1
- Match status: `matched`
- Selected match: storage [module] (target:target4:storage:storage:module:-) @ storage/__init__.py:1
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | storage [module] (target:target4:storage:storage:module:-) @ storage/__init__.py:1 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| storage | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

### Source: storage.repository

- Source: storage.repository [module] (source:source:storage.repository:storage.repository:module:-) @ storage/repository.py:1
- Match status: `matched`
- Selected match: storage.repository [module] (target:target4:storage.repository:storage.repository:module:-) @ storage/repository.py:1
- Overall confidence: 1

Candidates (1/1):

| # | Candidate | Overall | Explanation |
|---|---|---|---|
| 1 | storage.repository [module] (target:target4:storage.repository:storage.repository:module:-) @ storage/repository.py:1 | 1 |  |

Metric breakdown:

| Candidate | Overall | ast | mod | name | doc | penalty | module_distance |
|---|---|---|---|---|---|---|---|
| storage.repository | 1 | 1 | 1 | 1 | 0 | 0 | 1 |

## Results

| Project | Result ID | Category | Severity | Status | Rule | Source | Target | Location | Message |
|---|---|---|---|---|---|---|---|---|---|
| target4 | 3eb054b812f0098d | api_signature | error | FAILED | API001/required_entity_signature/v1 | checkout:CheckoutService.checkout |  | checkout.py:23 | Required target entity missing or not matchable (status=low_confidence, confidence=0.7). |
| target4 | 873e92652c3bd881 | api_signature | error | FAILED | API002/required_method/v1 | checkout:CheckoutService.checkout |  | checkout.py:23 | Required target entity missing or not matchable (status=low_confidence, confidence=0.7). |
| target4 | 9846a503c07429ab | protocol_conformance | error | FAILED | PRO001/implements_protocol/v1 | storage.repository:InMemoryOrderRepository |  | storage/repository.py:16 | Required target entity missing or not matchable (status=unmatched, confidence=0.0). |
| target4 | 7e83151de5b92f67 | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Order | models:Order | models.py:72 | OK |
| target4 | b6859173145a0bcb | attribute_contract | error | OK | API003/required_attribute/v1/d0 | models:Product | models:Product | models.py:18 | OK |
| target4 | 0f2c033f89a93896 | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Order | models:Order | models.py:72 | OK |
| target4 | 3ff56a7271b4e9b6 | attribute_contract | error | OK | API003/required_attribute/v1/d1 | models:Product | models:Product | models.py:18 | OK |
| target4 | 62b44478c114d316 | attribute_contract | error | OK | API003/required_attribute/v1/d2 | models:Order | models:Order | models.py:72 | OK |
| target4 | caa58c5548ea3a2d | attribute_contract | error | OK | API003/required_attribute/v1/d2 | models:Product | models:Product | models.py:18 | OK |
| target4 | a972d99020b1db6e | attribute_contract | error | OK | API003/required_attribute/v1/d3 | models:Order | models:Order | models.py:72 | OK |
| target4 | ed2c18f87c3de084 | api_signature | error | OK | API003/required_constructor/v1 | models:Product | models:Product | models.py:18 | OK |
| target4 | 6277ee188354a804 | api_signature | error | OK | API004/required_factory/v1 | models:Cart.empty | models:Cart.empty | models.py:48 | OK |
| target4 | dc84d4096ed027fc | api_signature | error | OK | API004/required_factory/v1 | models:Order.from_cart | models:Order.from_cart | models.py:105 | OK |
| target4 | b5472d69aacb78b4 | import_policy | error | OK | DEP001/forbid_imports/v2 | storage:storage | storage:storage | storage/__init__.py:1 | OK |
| target4 | 9664a29d3e26af62 | api_signature | warning | SKIPPED | API001/required_entity_signature_return/v1 | checkout:CheckoutService.checkout |  | checkout.py:23 | Rule skipped due to matching status low_confidence (confidence=0.7). |
