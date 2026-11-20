"""A declared dependency: its one parse and its one form (keyword: blocked-by).

``named`` is the one parse of "blocked" (plan 4.3, 6.1): ``Cannot be worked on
until <owner/repo#n> has merged``, ``Blocked by``, ``Blocked on`` or ``Depends on``
(any case; a bare ``#n`` is of the text's repository; pitboss#163, #280), in a
ticket, a comment or a PR body, for the walk and the gate alike. The form a PR body
writes is ``Blocked-by: owner/name#N`` (or ``#N``) on a line of its own, one
reference to a line (quire#1116); ``findings`` refuses a line that starts like one
and is not the form, so a dependency is never lost to a typo.
"""

import re
from typing import Sequence

# a bare ``#n`` is a ticket of the blocked item's own repository
ITEM = r"(?:[\w.-]+/[\w.-]+)?#\d+"
BLOCKER = re.compile(
    r"(?:cannot\s+be\s+worked\s+on\s+until|blocked[\s-]+(?:by|on)|depends\s+on):?\s+"
    rf"(?P<items>{ITEM}(?:(?:\s*,)?\s+(?:and\s+)?{ITEM}|\s*,\s*{ITEM})*)",
    re.IGNORECASE,
)
NAMED = re.compile(r"(?P<repo>[\w.-]+/[\w.-]+)?#(?P<number>\d+)")

LOOSE = re.compile(r"\W*blocked\b", re.I)  # a line that starts like a block
REFERENCE = re.compile(r"(?:[\w.-]+/[\w.-]+)?#\d+")
FORM = re.compile(r"^Blocked-by: (?:[\w.-]+/[\w.-]+)?#\d+$")
STARTS = re.compile(r"^[\W_]*blocked[\s_-]*(?:by|on)\b", re.IGNORECASE)
NOTE = 'the form is one line "Blocked-by: owner/name#N" for each blocker'


def named(text: str, slug: str) -> Sequence[str]:
    """The tickets and PRs a text says it cannot be worked on until.

    Args:
        text: a ticket's body, one of its comments, or a PR's body.
        slug: the repository of a bare ``#n``, ``owner/name``.

    Returns:
        The references as ``owner/name#number``, in the order of the text; a
        list (``x/y#4 and #9``, ``#3, #4``) names each of its items.
    """
    return [
        f"{each['repo'] or slug}#{each['number']}"
        for listed in BLOCKER.finditer(text)
        for each in NAMED.finditer(listed["items"])
    ]


def unnamed(body: str) -> Sequence[str]:
    """The lines of a body that start with ``blocked`` and name no item.

    Args:
        body: the PR body.

    Returns:
        Each such line.
    """
    return [
        line
        for line in body.splitlines()
        if LOOSE.match(line) and not REFERENCE.findall(line)
    ]


def findings(name: str, body: str) -> Sequence[str]:
    """The lines of a body that start like a dependency and are not the form.

    Args:
        name: what to call the body in a finding.
        body: the PR body.

    Returns:
        One finding for each such line, ending with ``(blocked-by)``.
    """
    return [
        f'{name}: "{row.strip()}" is not a dependency line: {NOTE} (blocked-by)'
        for row in body.splitlines()
        if STARTS.match(row) and not FORM.match(row)
    ]
