"""The ``Deviations:`` line of a hand-back (keyword: deviations, pitboss#257).

A worker told to change files with the Edit tool only was not caught when it
used ``sed``, a heredoc or ``rm`` until it said so itself. A hand-back now has a
``Deviations:`` line (the rules of the brief the worker broke, or ``none``), and
a hand-back without it is ``NOT STARTED`` and is sent back.
"""

PREFIX = "Deviations:"
NOT_STARTED = (
    "NOT STARTED: the hand-back has no `Deviations:` line (the rules of the brief"
    " you broke, or `none`)"
)


def line(handback: str) -> str:
    """The text of the ``Deviations:`` line of a hand-back.

    Args:
        handback: the hand-back text.

    Returns:
        What follows the prefix on the first line that starts with it, stripped;
        empty when there is no such line or nothing follows the prefix.
    """
    for each in handback.splitlines():
        if each.startswith(PREFIX):
            return each[len(PREFIX) :].strip()
    return ""


def not_started(handback: str) -> str:
    """The ``NOT STARTED`` text for a hand-back, empty when it has the line.

    Args:
        handback: the hand-back text.

    Returns:
        The text the orchestrator sends back, empty when the hand-back has a
        ``Deviations:`` line that says something.
    """
    return "" if line(handback) else NOT_STARTED
