"""A Done-when item that is a hoped-for share or count (keyword: hoped-figure, T419).

Owner (Moshe, 2026-11-09): "I might have said I hoped for a given percentage. But
that was never part of the criteria." A line asking for "at least N%", "N of M" or
"below N" of a population as the pass bar is not a criterion: each item names a
specific catch.
"""

import re
from typing import Sequence

from . import ticketwhen

LABEL = "hoped-figure"
SHOWN = 100
RULE = (
    "a figure the owner hoped for is not a criterion (Moshe, 2026-11-09:"
    ' "I might have said I hoped for a given percentage. But that was never part'
    ' of the criteria."); name the specific catch instead'
)
_SHARE = re.compile(
    r"\b(?:at\s+least|at\s+most|no\s+more\s+than|fewer\s+than|below|above|over|under)"
    r"\s+\d+(?:\.\d+)?\s*(?:%|percent|of\s+the\b|of\s+all\b)"
    r"|\b\d+(?:\.\d+)?\s*%"
    r"|\b\d+\s+of\s+(?:the\s+)?\d+\b",
    re.IGNORECASE,
)


def findings(ticket: str) -> Sequence[str]:
    """The findings for Done-when items that put a share or a count as the bar.

    Args:
        ticket: the ticket's text.

    Returns:
        One finding for each such item, none when each names a specific catch.
    """
    return [
        f"{LABEL}: the ticket's Done-when item `{each[:SHOWN]}` is a hoped-for"
        f" share or count; {RULE}"
        for each in ticketwhen.items(ticket)
        if _SHARE.search(each)
    ]
