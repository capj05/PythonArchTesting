# Matching variants

Should a name match weigh more when the scores leave an entity unpaired? E2
([evaluation](../../docs/dev_notes/evaluation-f5-2026-10-31.md)) found
solutions that name their modules differently leave every runtime rule
unpaired: the entry function, the only one of its name and arity, scored
0.27 against a minimum of 0.5. Changing the matching changes every target's
pairing, so variants were measured first on every example target whose
correct pairing is known, and the one adopted is `[matching] name_fallback`
([reporting.md](../../docs/reporting.md#pairing-by-name)).

```bash
python example/matching_weights/measure.py     # writes results.md
```

[`measure.py`](measure.py) says how the correct pairing is known for each
dataset and what each variant does; [results.md](results.md) has the counts,
every wrong pairing, every pairing without a known target (each judged by
hand) and the entities left unpaired.

## Findings

- Raising the name's weight in stage 3 (0.45 instead of 0.30) changed
  nothing: an entity in a renamed module with another body still scores below
  the minimum.
- Pairing the only entity of a name, then the methods of paired classes,
  pairs all 124 entities the scores left unpaired in the 12 solutions written
  without a skeleton, with no wrong pair, and 11 of the 12 in the hand-made
  mutants (the one left changed its signature, which the check refuses). The
  pairs without a known target are the same classes moved into a merged
  module (E08, E03, the adapters of program 2), correct by hand.
- A first version also paired a method by its name alone. The rule showcase
  showed why not: `api002_method/target_fail_declared_only` inherits
  `internal_check` from a base class, and the only method of that name, the
  base class's, was paired with the reference's `Service.internal_check`, so
  a target meant to fail passed. Methods are now paired only through their
  class. The emulated variants `unique_name*` in the table still do it, for
  the record.
- Built in (`engine_name_fallback`), the rules are stricter than the
  emulated ones, after a review found wrong pairs they could make on
  constructed cases none of these datasets holds: a weak but correct best
  candidate overridden by an unrelated same-named function, a class paired
  with a same-named class lacking its methods, a module paired by name, two
  reference entities of one name competing for one target. Now only
  top-level classes and functions are paired by name, a class must have the
  reference class's methods, a weak best candidate elsewhere is kept, the
  reference's name must be unique, and a target another unmatched entity
  scores higher for is left to it; inside a paired class the method name
  still outweighs a weak guess. An assisted mapping is applied before these
  rules and so always wins. The numbers stay: all 124 in E2, 11 of 12 in the
  mutants, and on the rule showcase 4 of the 8 entities the scores missed,
  with no pair without a known target added; the one wrong pair in that set
  is the scores' own. `tests/unit/test_matching/test_name_fallback.py` holds
  the constructed cases.

Effect on the evaluations, with `name_fallback` on:

- E2 without the assisted mapping: the runtime model runs on all 12 solutions
  written without a skeleton (before: unpaired on all 12), and every runtime
  marker is paired; only `module_interface` of program 1, declared on a
  renamed module, still needs the mapping. With the mapping the results are
  as before.
- The mutants: every mutant is caught as before, held-out sets unchanged.
  The equivalent rewrites E02 and E03 of program 2 (adapters merged into one
  module) no longer fail `implements_protocol`, and E08 of program 1 (three
  modules in one) fails only the static model and `forbid_runtime_imports`,
  declared on a merged module, instead of ten markers.

## Limits

The targets are the project's own examples and LLM-written solutions: none
is adversarial. A rule that pairs by name pairs an entity with a same-named
one wherever it is; that is what a teacher wants from a renamed module, and
the location is what the architecture rules then judge.
