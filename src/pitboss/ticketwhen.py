"""A ticket's Done-when, read from its body alone (keyword: plan-done-when).

Owner, 2026-11-08T23:06Z (pitboss#396): "NOT ADDING STUFF IN COMMENTS, ONLY BY
EDITING THE BODY, AND ONLY BEFORE A WORKER HAS STARTED". The Done-when of a
ticket is its own section (a ``Done when`` heading or line, up to the next
heading) and nothing else: a comment, whatever it says, adds nothing to it.
``items`` lists the section's bullets (a paragraph of lines is one), so
``pitboss plan-check`` can hold a Plan to them word for word, and ``digest`` is
the record of the section that the brief prints and the PR body keeps, so a
section edited after a worker started is found. The module reads nothing: the
ticket's text is given.
"""

import hashlib
import re
from typing import Sequence

SECTION = re.compile(
    r"(?ims)^(?:#+[ \t]*)?(?:\*\*)?Done[- ]when\b([^\n]*)\n"
    r"(.*?)(?=^#+[ \t]|^---[ \t]*$|\Z)"
)
# a bullet's marker, after its indentation: `-`, `*`, `+`, `1.` or `1)`
BULLET = re.compile(r"^(\s*)(?:[-*+]|\d{1,3}[.)])\s+(.*)$")
LENGTH = 16


def _lines(ticket: str) -> Sequence[str]:
    found = SECTION.search(ticket)
    if found is None:
        return []
    first = found.group(1).strip(" \t:*")
    return [first, *found.group(2).splitlines()]


def items(ticket: str) -> Sequence[str]:
    """The bullets and paragraphs of a ticket's own Done-when section.

    A bullet runs over the lines that follow it until a blank line or the next
    bullet of its level (a deeper bullet is part of it); a paragraph of lines
    with no bullet is one item. A bullet's marker is not part of its text.

    Args:
        ticket: the ticket's text.

    Returns:
        The text of each item, its lines joined by a space; the text after the
        colon of the heading's own line comes first.
    """
    found: list[list[str]] = []
    top: int | None = None
    open_item = False
    for line in _lines(ticket):
        if not line.strip():
            open_item = False
            continue
        marked = BULLET.match(line)
        deeper = marked is not None and top is not None and len(marked[1]) > top
        if marked is not None and not deeper:
            top = len(marked[1]) if top is None else top
            found.append([marked[2].strip()])
            open_item = True
        elif open_item:
            found[-1].append(line.strip())
        else:
            found.append([line.strip()])
            open_item = True
    return [" ".join(" ".join(each).split()) for each in found]


def digest(ticket: str) -> str:
    """The record of a ticket's Done-when.

    Args:
        ticket: the ticket's text.

    Returns:
        The first 16 hex digits of the SHA-256 of the items, a line each; empty
        when the ticket has no Done-when.
    """
    found = items(ticket)
    if not found:
        return ""
    return hashlib.sha256("\n".join(found).encode("utf-8")).hexdigest()[:LENGTH]
