"""The sweep's RULING DUE and PAUSE lines (keyword: round-limit)."""

from typing import Sequence

from . import pulls, roundlimit
from .markers import Marker

LINES = {
    roundlimit.Limit.RULING_DUE: (
        Marker.RULING_DUE,
        "the review rounds hit the changes-needed limit and no ruling is"
        " recorded; start an Opus agent whose only brief is to make a ruling,"
        " record it as a PR comment whose first line is"
        f" {roundlimit.RULING_FIRST_LINE!r}; the PR is offered for no fix,"
        " update or review round until then, and its other action lines wait",
    ),
    roundlimit.Limit.PAUSE: (
        Marker.PAUSE,
        "changes needed again after the Opus ruling; label the PR and its"
        " ticket paused-owner with a comment of what the rounds disagreed"
        " about and the options, stop listing both, and report the number and"
        " the options to the owner; the PR is offered for no fix, update or"
        " review round, and its other action lines wait",
    ),
}


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The line of a PR whose review rounds hit the changes-needed limit.

    Args:
        pull: the PR.

    Returns:
        One line, RULING DUE or PAUSE, or none when the limit holds nothing.
    """
    found = LINES.get(pull.limit)
    if found is None:
        return []
    marker, action = found
    return [f"{marker.text} {pulls.reference(pull)}: {action}"]
