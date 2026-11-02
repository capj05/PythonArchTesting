"""Clinic appointments: book, cancel and reschedule visits, remind patients.

The program is one package in layers, each layer a subpackage: ``domain``
(patients, slots, appointments, cancellation policies, events), ``ports``
(what the application needs from the outside, as protocols), ``application``
(the use cases and the event bus), ``adapters`` (stores, notifier, clocks)
and ``api`` (request handlers). ``wiring`` composes them.
"""
