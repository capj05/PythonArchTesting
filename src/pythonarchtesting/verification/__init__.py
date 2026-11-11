"""Checks of what an author proposes for a reference, run on the reference.

``cases`` runs proposed cases of an entity and judges them; ``marker``
seeds violations into copies of a reference and checks that a marker catches
them; ``mutant_runs`` holds what both mutation checks share: the copies of a
reference with one mutant each, the outcome of a rule on one copy, and the
choice of mutants under a limit. A task's verification
(``principles.task_verification``) builds on them.
"""
