"""A ticket that lists a row the source table marks as not a test to pass (pitboss#279).

quire#828 said "Every ``must`` test passes" over 11 rows, 10 of which the table
of #827 had already marked ``policy`` or ``platform``: no worker could deliver
it, and it sat 12 days in the queue as ready work (keyword: rows-pass).
"""

import re
from typing import Sequence

CHECK = "rows-pass"
TAGS = ("policy", "platform", "decision")
SHOWN = 80
_DONE_WHEN = re.compile(r"Done-when[ \t]*:?[ \t]*\n*(.*?)(?:\n[ \t]*\n|\Z)", re.DOTALL)
_EVERY = re.compile(
    r"\b(?:every|each|all)\b[^.\n]{0,60}?\b(?:rows?|tests?|cases?)\b[^.\n]{0,40}?"
    r"\bpass(?:es)?\b",
    re.IGNORECASE,
)
_TAG = "|".join(TAGS)
_CELL = re.compile(rf"^[\s`*_()\[\]]*(?:{_TAG})[\s`*_()\[\]]*$", re.IGNORECASE)
# in a list item a bare word is prose: the tag is in backticks, brackets or parentheses
_MARK = re.compile(rf"[`(\[](?:{_TAG})[`)\]]", re.IGNORECASE)
_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")


def _promised(body: str) -> bool:
    return any(_EVERY.search(each) for each in _DONE_WHEN.findall(body))


def _tagged(line: str) -> bool:
    if line.lstrip().startswith("|"):
        return any(_CELL.match(cell) for cell in line.strip().strip("|").split("|"))
    return bool(_ITEM.match(line)) and bool(_MARK.search(line))


def findings(name: str, body: str) -> Sequence[str]:
    """The rows a ticket marks as not to pass, under a Done-when that says all do.

    Args:
        name: the ticket's name, for the finding.
        body: the ticket's text.

    Returns:
        One finding for each row tagged ``policy``, ``platform`` or
        ``decision`` when the Done-when says every row, test or case passes.
    """
    if not _promised(body):
        return []
    return [
        f"{name}: the Done-when says every row passes, and this row is marked"
        f" policy, platform or decision ({CHECK}): {' '.join(line.split())[:SHOWN]}."
        " Rule 1: a piece's Done-when is never stricter than its parent's (every"
        " escape, such as `or is n/a with the reason written here`, carries over)."
        " Rule 2: a row marked `policy`, `platform` or `decision` is never listed"
        " as a row the ticket makes pass"
        for line in body.splitlines()
        if _tagged(line)
    ]
