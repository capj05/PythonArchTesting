# Assignment: clinic appointments (layered packages)

Write a Python package (a directory with `__init__.py`) that books, cancels
and moves appointments at a clinic and reminds patients. Use only the
standard library (`sqlite3` is allowed where stated). The package is organised
in layers, each layer a subpackage: `domain`, `ports`, `application`,
`adapters`, `api`, and a module `wiring.py` at the top.

## What it does

Time is counted as a day number (1, 2, …) and an hour; the clinic works
hours 8 to 15 (`WORKING_HOURS = range(8, 16)`).

- Domain:
  - `Patient(patient_id, name, email)`; an empty id or an e-mail without `@`
    is a `ValueError`; `greeting()` returns `"Dear <first name>"`.
  - `Slot(doctor, day, hour)` (a `ValueError` outside working hours or for a
    day below 1), equal and hashable by `(doctor, day, hour)`;
    `hours_from(day, hour)` is the number of hours from that moment to the slot.
  - `Appointment(appointment_id, patient_id, slot)` with `status` (`"booked"`,
    `"cancelled"`, `"attended"`), `fee` (0) and `history` (earlier slots);
    `active` is true while booked; `cancel(fee)`, `move_to(slot)` and
    `mark_attended()` change it and refuse (`ValueError`) an appointment that
    is not active. Its state changes only through these methods.
  - `free_slots(doctor, day, taken)`: the doctor's slots on that day not in
    the set `taken`, in time order.
  - Cancellation policies, each with `fee(appointment, day, hour)`:
    `FreeCancellation()` (always 0), `LateCancellationFee(hours, amount)`
    (`amount` when the visit starts within `hours` of the cancellation),
    `TieredFee(steps)` (the amount of the first `(hours, amount)` step the
    cancellation is within, else 0).
  - Events `AppointmentBooked(appointment_id, patient_id, when)`,
    `AppointmentCancelled(appointment_id, patient_id, fee)`,
    `AppointmentMoved(appointment_id, patient_id, when)`, each with a class
    attribute `name`: `"booked"`, `"cancelled"`, `"moved"`.
- Ports (`typing.Protocol`):
  - an appointment store: `add(appointment)`, `get(appointment_id)` (or
    `None`), `holding(slot)` (the active appointment in that slot, or `None`),
    `on_day(day)` (that day's appointments by hour), `next_id()` (`"A1"`,
    `"A2"`, …);
  - a patient store: `add(patient)`, `get(patient_id)`;
  - a notifier: `send(address, subject, body)`;
  - a clock: `now()` returning `(day, hour)`.
- Application:
  - `EventBus()` with `subscribe(name, handler)`, `unsubscribe(name, handler)`
    and `publish(event)`, which calls every handler subscribed to the event's
    `name`, in order.
  - `BookingService(appointments, patients, clock, policy, bus)`:
    - `register(patient_id, name, email)` adds a new patient (or returns the
      known one);
    - `book(patient_id, doctor, day, hour)` books a free slot in the future for
      a known patient, stores it, publishes `AppointmentBooked` and returns the
      appointment; an unknown patient, an invalid, past or taken slot is a
      `BookingError` (a class of yours);
    - `cancel(appointment_id)` cancels with the fee the policy gives for now,
      publishes `AppointmentCancelled` and returns the fee;
    - `move(appointment_id, day, hour)` moves to another free slot of the same
      doctor and publishes `AppointmentMoved`;
    - `free(doctor, day)` lists the doctor's free slots that day.
  - `ReminderService(appointments, patients, notifier)`: `listen(bus)`
    subscribes it to the three events, and each sends the patient an e-mail
    (subject `"Appointment booked"`, `"Appointment moved"`,
    `"Appointment cancelled"`); `run_for(day)` sends a `"Reminder"` for every
    active appointment that day and returns how many it sent. Every body
    starts with the patient's greeting.
- Adapters: `InMemoryAppointmentStore(appointments=None)`,
  `InMemoryPatientStore(patients=None)`, `SqliteAppointmentStore(path=":memory:")`
  (the same store in SQLite; it must also see changes made to the appointments
  it handed out), `OutboxNotifier()` (keeps the sent e-mails as
  `(address, subject, body)` in a list `sent`), `FixedClock(day, hour)` and
  `SystemClock(start)` (days counted from the date `start`).
- Request handlers (`api`), each taking a request `dict` and the service and
  returning `{"status": "ok", …}` or `{"status": "error", "reason": <text>}`:
  `book` (`patient`, `name`, `email`, `doctor`, `day`, `hour`; answers
  `appointment`, a dict with `id`, `patient`, `doctor`, `day`, `hour`,
  `status`, `fee`), `cancel` (`appointment`; answers `fee`), `move`
  (`appointment`, `day`, `hour`; answers `appointment`), `free` (`doctor`,
  `day`; answers `hours`), and `remind(request, reminders)` (`day`; answers
  `sent`). A missing field or a non-number day/hour is an error answer.
- `wiring.py`: `build(day=1, hour=8, sqlite=False)` composes the application
  (the in-memory or SQLite appointment store, an in-memory patient store, the
  outbox notifier, a fixed clock, `LateCancellationFee(hours=24, amount=30)`,
  one bus, the reminders listening on it) and returns a dict with `booking`,
  `reminders` and `notifier`; `serve(requests, day=1, hour=8, sqlite=False)`
  builds it and answers a list of requests in order, each with an `action`
  (`book`, `cancel`, `move`, `free`, `remind`; anything else is an error
  answer).

## Architecture (graded)

1. `domain` depends on nothing outside `domain` and uses no I/O library.
2. `application` depends only on `domain` and `ports`, never on `adapters`,
   `api` or `wiring`.
3. The request handlers talk to the application only: not to adapters, ports
   or the domain directly, not even through objects reachable from the service.
4. `sqlite3` (and libraries like `pickle`) only in the SQLite adapter.
5. Every adapter satisfies its port.
6. Adapters are built only in `wiring.py`; everything else gets them injected.
7. Events go through the bus; the reminders send every message through the
   injected notifier.
8. The cancellation policy is injected and used for every fee.
9. No dependency cycles between modules.
10. Other modules use the schedule (slots and appointments) only through
    `Slot`, `Appointment`, `free_slots` and `WORKING_HOURS`.
11. An appointment's state changes only through its own methods.
12. One layer order: `wiring` on top; `api` and `adapters` below it,
    independent of each other; then `application`; then `ports`; then
    `domain`. A higher layer may use a lower one, never the reverse.
