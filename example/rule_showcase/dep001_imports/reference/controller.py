"""Reference controller; declares import policy via module-level marker.

The single ``__archtest__`` marker forbids ``telnetlib`` from being reachable
from this module under ``mode="reachable"``. ``warnings`` is explicitly
allowed as an exception, ``ignore_type_checking`` skips imports guarded by
``if TYPE_CHECKING:``, and ``ignore_globs`` masks helper modules whose
imports must not contribute to the reachable graph.
"""

from typing import Annotated

from pythonarchtesting.rules import forbid_imports

from .helper_clean import helper_action

# Module-level rule declaration: scope=module, mode=reachable.
# Forbidden module:        telnetlib  (stdlib, deprecated -- easy to spot)
# Allowed exception:       warnings   (stdlib, explicitly tolerated)
# Type-checking imports:   ignored
# Glob-excluded modules:   reference/ignored_module.py
__archtest__: Annotated[
    None,
    forbid_imports(
        "telnetlib",
        scope="module",
        mode="reachable",
        ignore_type_checking=True,
        allow=("warnings",),
        ignore_globs=("**/ignored_module.py",),
    ),
]


def do_work() -> None:
    """Reference controller body -- no forbidden imports here."""
    helper_action()
