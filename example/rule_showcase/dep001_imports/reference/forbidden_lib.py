"""Stand-in module used by some failing targets to reach ``telnetlib``.

In the reference this module is empty so the AST parser sees no forbidden
imports. Targets that should fail the reachable-graph check overwrite this
file with a ``import telnetlib`` line.
"""
