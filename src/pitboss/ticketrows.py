"""A ticket that lists a row its table marks as not to pass (pitboss#279).

quire#828 said "Every ``must`` test passes" over 11 rows, 10 of which the table
of #827 had already marked ``policy`` or ``platform``: no worker could deliver
it, and it sat 12 days in the queue as ready work (keyword: rows-pass).
"""

import argparse
import re
from typing import Sequence

from . import config, forms

CHECK = "rows-pass"
TAGS = ("policy", "platform", "decision")
SHOWN = 80
_PROMISE = re.compile(
    r"\b(?:every|each|all)\b[^.\n]{0,60}?\b(?:rows?|tests?|cases?)\b[^.\n]{0,40}?"
    r"\bpass(?:es)?\b",
    re.IGNORECASE,
)
_BARE = "|".join(TAGS)
_CELL = re.compile(rf"^\W*(?:{_BARE})\W*$", re.IGNORECASE)
# in a list item a bare word is prose: the tag is in backticks, brackets or parentheses
_MARK = re.compile("[`(\\[](?:" + _BARE + ")[`)\\]]", re.IGNORECASE)
_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")


def _promised(body: str) -> bool:
    # the paragraph after "Done-when", on its line or under its heading
    parts = body.split("Done-when")[1:]
    paragraphs = ["\n".join(part.lstrip(" \t:\n").split("\n\n")[:1]) for part in parts]
    return any(_PROMISE.search(each) for each in paragraphs)


def _tagged(line: str) -> bool:
    if line.lstrip().startswith("|"):
        return any(_CELL.match(cell) for cell in line.strip().strip("|").split("|"))
    return bool(_ITEM.match(line) and _MARK.search(line))


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


def check(
    args: argparse.Namespace, subject: forms.Subject, settings: config.Lint
) -> Sequence[str]:
    """The form check of ``pitboss lint ticket``.

    Args:
        args: the parsed arguments (not read).
        subject: the ticket.
        settings: the lint settings (not read).

    Returns:
        The findings.
    """
    return findings(subject.name, subject.body)
