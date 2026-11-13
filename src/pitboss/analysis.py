"""The ``How we got here`` section of an escalation (keyword: how-we-got-here).

An escalation, whether to an Opus ruling or to the owner, carries an analysis of
how the work got there (dev-skill-up/pitboss#168): for each rejection before it,
the finding, the rule or brief line that should have prevented it, and the
prevention filed (a pitboss ticket number). This module reads whether a text has
the section; the ruling form, the owner's pause and ``lint owner-card`` use it.
"""

import re

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
