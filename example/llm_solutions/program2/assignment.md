# Assignment: library lending (ports and adapters)

Write a Python package (a directory with `__init__.py`) that lends library
books, in the ports-and-adapters (hexagonal) style. Use only the standard
library. Keep it small; no I/O, no persistence.

## What it does

- `Loan(book_id, member, due)` keeps `book_id`, `member`, `due` (a day
  number) and `returned` (initially `False`); `close()` marks it returned,
  `is_overdue(today)` is true for a loan not returned after its due day.
- The application needs three things from the outside world, as ports
  (`typing.Protocol`): a loan store (`add(loan)`, `find(book_id)` returning
  the loan or `None`), a notifier (`send(member, text)`) and a clock
  (`today()` returning a day number).
- `LendingService(store, notifier, clock, period=14)`:
  - `lend(book_id, member)` refuses (`ValueError`) a book that is lent and
    not returned; otherwise it creates a loan due `period` days after today,
    adds it to the store, notifies the member with a text naming the book and
    the due day, and returns the due day;
  - `give_back(book_id)` closes the open loan of the book and returns
    `True`, or returns `False` when there is none.
- Adapters: `InMemoryLoanStore(loans=None)`, `FixedClock(day)` and
  `OutboxNotifier()`, which keeps the sent messages as `(member, text)` in a
  list `sent`.
- Request handlers: `lend_book(request, service)` takes
  `{"book": str, "member": str}`; a missing book or member gives
  `{"status": "error", "reason": "book and member are required"}`, otherwise
  `{"status": "ok", "due": <due day>}`. `return_book(request, service)` gives
  `{"status": "ok"}` or `{"status": "not_lent"}`.
- `build(day=1)` wires a `LendingService` with the in-memory store, the
  outbox notifier and a fixed clock.

## Architecture (graded)

1. The domain (the loan) depends on nothing else in the package.
2. The application uses the ports, never the adapters: it does not import or
   create adapter classes and works with what it was given.
3. Each adapter satisfies its port.
4. The request handlers talk to the application only, never to adapters or
   the store, not even through the service's attributes or a helper.
5. A loan is closed only through `Loan.close`.
6. Lending notifies through the injected notifier.
7. One layer order: the composition root (`build`) on top; the request
   handlers and the two kinds of adapters below it, independent of each
   other; then the application; then the ports; then the domain. A higher
   layer may use a lower one, never the reverse.
8. No dependency cycles between modules.
