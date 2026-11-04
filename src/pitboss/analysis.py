"""The ``How we got here`` section of an escalation (keyword: how-we-got-here).

An escalation, whether to an Opus ruling or to the owner, carries an analysis of
how the work got there (dev-skill-up/pitboss#168): for each rejection before it,
the finding, the rule or brief line that should have prevented it, and the
prevention filed (a pitboss ticket number). This module reads whether a text has
the section; the ruling brief, the sweep's ``RULING NO ANALYSIS`` line and
``lint owner-card`` use it.
"""

import re
from typing import AbstractSet, Sequence

from . import flowstate, shapes

SECTION = "How we got here"
_SECTION = re.compile(
    r"^[ \t]*(?:#+[ \t]*)?\**How[ \t]+we[ \t]+got[ \t]+here\b\**[ \t]*:?\**(.*)\Z",
    re.MULTILINE | re.IGNORECASE | re.DOTALL,
)


def has_section(body: str) -> bool:
    """Whether a text has a ``How we got here`` section with something in it.

    The section starts at a line that is the words (a heading, bold or followed
    by a colon, and the analysis may follow on the same line) and runs to the end
    of the text.

    Args:
        body: the comment or card text.

    Returns:
        True when a line starts with the words and anything follows them.
    """
    found = _SECTION.search(body)
    return bool(found and found.group(1).strip())


def unanalysed(
    posted: Sequence[shapes.Comment], trusted: AbstractSet[str]
) -> Sequence[str]:
    """The newest Opus ruling comment that has no ``How we got here`` section.

    Args:
        posted: the PR's issue comments.
        trusted: the author associations whose rulings count.

    Returns:
        Its address in a list, or an empty list when there is no ruling or the
        newest one has the section.
    """
    rulings = [
        each
        for each in posted
        if flowstate.is_ruling(each.body) and each.author_association in trusted
    ]
    newest = max(rulings, key=lambda each: each.created_at, default=None)
    if newest is None or has_section(newest.body):
        return []
    return [newest.url]
