"""The sweep's RULING DUE and PAUSE lines, from the flow (keyword: review-flow)."""

from typing import Sequence

from . import pulls, steps
from .markers import Marker

LINES = {
    steps.Step.OPUS_RULING: (
        Marker.RULING_DUE,
        "the review rounds hit the changes-needed limit and no ruling is"
        " recorded; start an Opus agent whose only brief is to make a ruling,"
        " record it as a PR comment whose first line is"
        f" {steps.RULING_FIRST_LINE!r}; the PR is offered for no fix,"
        " update or review round until then, and its other action lines wait",
    ),
    steps.Step.PAUSE_FOR_OWNER: (
        Marker.PAUSE,
        "changes needed again after the Opus ruling; label the PR and its"
        " ticket paused-owner with a comment of what the rounds disagreed"
        " about and the options, stop listing both, and report the number and"
        " the options to the owner; the PR is offered for no fix, update or"
        " review round, and its other action lines wait",
    ),
}


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The line of a PR whose step asks for an Opus ruling or pauses it.

    Args:
        pull: the PR.

    Returns:
        One line, RULING DUE or PAUSE, or none for any other step.
    """
    found = LINES.get(pull.step.step)
    if found is None:
        return []
    marker, action = found
    return [f"{marker.text} {pulls.reference(pull)}: {action}"]
