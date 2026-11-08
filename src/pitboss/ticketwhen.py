"""A ticket's Done-when and the comments that add to it (keyword: plan-done-when).

The Done-when of a ticket is its own section (a ``Done when`` heading or line, up
to the next heading) and each comment that says ``Added to the Done-when`` (a
parenthesis of when and why may follow, then the item). ``expected`` lists them,
a line each, with where each came from, so ``pitboss plan-check`` can hold a
Plan's Done-when to them word for word (pitboss#317). The module reads nothing:
the ticket and its comments are given.
"""

import re
from typing import Sequence

SECTION = re.compile(
    r"(?ims)^(?:#+[ \t]*)?(?:\*\*)?Done[- ]when\b([^\n]*)\n"
    r"(.*?)(?=^#+[ \t]|^---[ \t]*$|\Z)"
)
ADDED = re.compile(r"\bAdded to (?:the )?Done[- ]when\b", re.IGNORECASE)
FOOTER = re.compile(r"\n---[ \t]*(?:\n|$)")
OPEN = "("
CLOSE = ")"


def _after_parenthesis(text: str) -> str:
    # the text after the parenthesis that opens it, which may hold others
    start = text.lstrip()
    if not start.startswith(OPEN):
        return text
    depth = 0
    for at, each in enumerate(start):
        depth += (each == OPEN) - (each == CLOSE)
        if depth == 0:
            return start[at + 1 :]
    return ""


def added_item(comment: str) -> str:
    """The item a comment adds to a ticket's Done-when.

    Args:
        comment: the comment's text.

    Returns:
        The text after ``Added to the Done-when`` and its parenthesis, without
        the generated-by footer; empty when the comment adds nothing.
    """
    found = ADDED.search(comment)
    if found is None:
        return ""
    rest = _after_parenthesis(comment[found.end() :])
    return FOOTER.split(rest.lstrip(" \t:.\n"))[0].strip()


def section_lines(ticket: str) -> Sequence[str]:
    """The lines of a ticket's own Done-when section.

    Args:
        ticket: the ticket's text.

    Returns:
        Each non-blank line, stripped; those on the heading's line after a colon
        come first.
    """
    found = SECTION.search(ticket)
    if found is None:
        return []
    first = found.group(1).strip(" \t:*")
    lines = [first, *found.group(2).splitlines()]
    return [each.strip() for each in lines if each.strip()]


def expected(ticket: str, comments: Sequence[str]) -> Sequence[tuple[str, str]]:
    """Every line a Plan's Done-when holds, and where it comes from.

    Args:
        ticket: the ticket's text.
        comments: the ticket's comments, oldest first.

    Returns:
        Each line of the ticket's section as ``("the ticket's Done-when", line)``
        and each line of each added item as ``("the comment ...", line)``.
    """
    found = [("the ticket's Done-when", each) for each in section_lines(ticket)]
    for number, comment in enumerate(comments, 1):
        item = added_item(comment)
        found.extend(
            (f"comment {number}'s added Done-when", each.strip())
            for each in item.splitlines()
            if each.strip()
        )
    return found
