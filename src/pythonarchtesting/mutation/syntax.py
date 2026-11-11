"""Whether a mutated module still parses, parsing only what the change
touched.
"""

from __future__ import annotations

import ast
import re

from pythonarchtesting.mutation.project import Module

# A line as Python's tokenizer counts lines: ``str.splitlines`` also breaks at
# ``\f``, ``\v``, ``\x1c``-``\x1e``, ``\x85``, `` `` and `` ``.
_LINE = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+\Z")


# The one ``__future__`` import that changes how later statements parse:
# ``<>`` for ``!=``. A text that names it is always parsed whole.
_PARSER_FUTURE = "barry_as_FLUFL"


def parses(text: str) -> bool:
    try:
        ast.parse(text)
    except SyntaxError:
        return False
    return True


class Syntax:
    """Whether a changed text of a module parses, parsing only the top-level
    statements the change touched.

    Between two top-level statements, each starting a line of its own at the
    left margin, the tokenizer holds nothing over: no open bracket or string,
    no indentation. A text that keeps the module's statements up to such a
    boundary and from another one on, and has between them a part that
    parses on its own and ends a line, parses whole: its statements are the
    kept ones and the part's, in turn. The part is parsed alone; when it does
    not parse so, or the change does not fit that shape, the whole text is
    (``ast.parse``), so the answer is always the whole text's. A mutant
    changes one place, so the part is a statement or two, not the file.
    """

    def __init__(self, module: Module) -> None:
        text = module.text
        self._text = text
        self._whole = _PARSER_FUTURE in text
        offsets = [0, *(match.end() for match in _LINE.finditer(text))]
        bounds = {0, len(text)}
        previous_end = 0
        for statement in module.tree.body:
            decorators = getattr(statement, "decorator_list", None) or []
            first = min([statement.lineno, *(d.lineno for d in decorators)])
            start = offsets[first - 1] if first - 1 < len(offsets) else None
            if (
                first > previous_end
                and start is not None
                and text[start : start + 1] not in ("", " ", "\t", "\f")
                and (start == 0 or text[start - 1] == "\n")
            ):
                bounds.add(start)
            previous_end = max(previous_end, int(statement.end_lineno or first))
        self._bounds = sorted(bounds)

    def parses(self, new: str) -> bool:
        """Whether ``new``, the module's text after a change, parses."""
        text, bounds = self._text, self._bounds
        if self._whole or _PARSER_FUTURE in new:
            return parses(new)
        # The last boundary up to which ``new`` keeps the text: bounds[0] = 0
        # always holds.
        low, high = 0, len(bounds) - 1
        while low < high:
            middle = (low + high + 1) // 2
            if new.startswith(text[: bounds[middle]]):
                low = middle
            else:
                high = middle - 1
        start = bounds[low]
        room = len(new) - start
        # The first boundary from which on ``new`` keeps the text, after
        # ``start``: the end of the text always holds (an empty rest).
        high = len(bounds) - 1
        while low < high:
            middle = (low + high) // 2
            kept = len(text) - bounds[middle]
            if kept <= room and new.endswith(text[bounds[middle] :]):
                high = middle
            else:
                low = middle + 1
        end = bounds[low]
        part = new[start : len(new) - (len(text) - end)]
        if end < len(text) and part and not part.endswith("\n"):
            return parses(new)  # the part runs on into the kept rest
        return parses(part) or parses(new)
