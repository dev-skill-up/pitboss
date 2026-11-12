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
BULLET = re.compile(r"^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$")
LENGTH = 16


def _lines(ticket: str) -> Sequence[str]:
    found = SECTION.search(ticket)
    if found is None:
        return []
    first = found.group(1).strip(" \t:*")
    return [first, *found.group(2).splitlines()]


def _top_bullet(line: str, top: int | None) -> re.Match[str] | None:
    # a bullet that is not deeper than the first one seen
    marked = BULLET.match(line)
    if marked is None or (top is not None and len(marked[1]) > top):
        return None
    return marked


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
    return [text for _, text in _marked(ticket)]


def bullets(ticket: str) -> Sequence[str]:
    """The bullets of a ticket's Done-when, each with the marker it was written with.

    Args:
        ticket: the ticket's text.

    Returns:
        The items that are bullets, each as ``MARKER TEXT`` (``* `` for a ticket
        written with ``* ``, ``1. `` for a numbered one), so a Plan copies it as
        the ticket has it (keyword: plan-done-when, pitboss#282); an item that is a
        paragraph has no marker and is not listed.
    """
    return [f"{marker} {text}" for marker, text in _marked(ticket) if marker]


def _marked(ticket: str) -> Sequence[tuple[str, str]]:
    # each item's marker (empty for a paragraph) and its text
    lines = _lines(ticket)
    # the level of the first bullet is the top level
    top = next((len(each[1]) for each in map(BULLET.match, lines) if each), None)
    found: list[tuple[str, list[str]]] = []
    for block in _blocks(lines):
        groups = _groups(block, top)
        # keyword: done-when-bullets (bats#654): once the list has begun, a paragraph
        # after it ("Found by ...", "Not in this ticket ...", "Priority: p0") is
        # not a Done-when item; a lead line before the first bullet is
        listed = any(marker for marker, _ in found)
        found.extend(groups[1:] if listed and groups and not groups[0][0] else groups)
    return [(marker, " ".join(" ".join(each).split())) for marker, each in found]


def _blocks(lines: Sequence[str]) -> Sequence[Sequence[str]]:
    # the runs of lines between blank lines
    blocks: list[list[str]] = [[]]
    for each in lines:
        if each.strip():
            blocks[-1].append(each)
        elif blocks[-1]:
            blocks.append([])
    return blocks


def _groups(block: Sequence[str], top: int | None) -> Sequence[tuple[str, list[str]]]:
    # a top-level bullet starts an item; a line that is none continues it
    groups: list[tuple[str, list[str]]] = []
    for line in block:
        marked = _top_bullet(line, top)
        if marked is not None:
            groups.append((marked[2], [marked[3].strip()]))
        elif groups:
            groups[-1][1].append(line.strip())
        else:
            groups.append(("", [line.strip()]))
    return groups


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
