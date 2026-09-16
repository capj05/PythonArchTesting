"""target_fail_module_scope -- two-hop reachable chain to ``telnetlib``.

Chain: controller -> helper_clean -> forbidden_lib -> telnetlib.
The reachable-graph traversal must follow both edges and flag the violation.
"""

from .helper_clean import helper_action


def do_work() -> None:
    helper_action()
