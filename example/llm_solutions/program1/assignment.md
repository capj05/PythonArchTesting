# Assignment: a small order shop

Write a Python package (a directory with `__init__.py`) that places orders.
Use only the standard library. Keep it small; no I/O, no persistence.

## What it does

- A request handler `handle_order(request, service)` takes a request
  `{"id": str, "prices": list[float]}` and an order service. An empty or
  missing price list gives `{"status": "error", "reason": "empty order"}`;
  otherwise the service places the order and the handler returns
  `{"status": "ok", "total": <the order's total>}`.
- `OrderService(repository, discount, bus)` has `place(order_id, prices)`,
  which creates an `Order`, adds the prices, applies the discount strategy to
  the total, marks the order placed, saves it in the repository, publishes
  the event `"order_placed"` with the order id on the bus, and returns the
  total.
- `Order(order_id)` keeps `order_id`, `items`, `total` and `status` (`"new"`,
  then `"placed"`), and has `add(price)`, `apply_total(total)` and
  `mark_placed()`.
- `OrderRepository()` keeps orders in memory: `save(order)`, `get(order_id)`.
- Discount strategies: `NoDiscount()` and `PercentDiscount(percent)`, each
  with `apply(total)` returning the new total (percent discount rounded to
  two decimals).
- `EventBus()` with `subscribe(listener)`, `unsubscribe(listener)` and
  `publish(event, payload)`, which calls every subscribed
  `listener(event, payload)`.
- `AppConfig` with a `currency` of `"CZK"`, shared as one instance through
  `AppConfig.instance()`.

## Architecture (graded)

1. Layers: the request handler (presentation) uses only the order service;
   the service is the only layer that uses storage. The handler must never
   reach the repository, not even through the service's attributes or a
   helper.
2. The service gets its repository, discount strategy and event bus from
   its constructor and uses exactly those: it never imports or creates them.
3. An order changes only through its own methods.
4. No persistence or serialisation technology (`sqlite3`, `pickle`) in the
   service.
5. The discount is computed by the injected strategy.
6. The event bus is an observer: subscribing, unsubscribing and publishing
   behave as described.
7. The configuration is a singleton.
8. No dependency cycles between modules.
