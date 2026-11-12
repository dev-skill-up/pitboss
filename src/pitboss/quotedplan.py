"""The Plan rows quote the ticket's Done-when, so their quotes are not read as claims.

A numbered row of the Plan is a bullet of the ticket's Done-when word for word
(``plan-done-when`` holds it to that), and a Done-when may name a phrase the
phrase lint refuses ("D4 (never say "I haven't checked")"): the row quotes the
rule, it does not break it (keyword: plan-quote, pitboss#444). ``mask`` blanks
the quoted part of each row, up to its ``CI:`` pointer, and keeps every line
number; the pointer and every other line are read as before. The module reads
nothing, as the body is given.
"""

import re

PLAN = re.compile(r"^##[ \t]+Plan[ \t]*$")
HEADING = re.compile(r"^##[ \t]")
ROW = re.compile(r"^(\s*\d{1,9}[.)]\s+)(.*?)((?:[ \t]CI:.*)?)$")


def _masked(line: str) -> str:
    found = ROW.match(line)
    return line if found is None else found[1] + " " * len(found[2]) + found[3]


def mask(body: str) -> str:
    """The body with the quoted text of each numbered Plan row blanked.

    Args:
        body: the PR's body.

    Returns:
        The body whose numbered rows of the ``## Plan`` section are blank up to
        their `` CI:`` pointer (the whole row when it has none), line for line.
    """
    inside = False
    kept: list[str] = []
    for line in body.split("\n"):
        inside = bool(PLAN.match(line)) or (inside and not HEADING.match(line))
        kept.append(_masked(line) if inside else line)
    return "\n".join(kept)
