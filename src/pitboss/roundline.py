"""The sweep's lines of the steps about an Opus ruling (keyword: review-flow).

RULING DUE, PAUSE, RULING UNREADABLE and RULING ESCALATES, from the flow.
"""

from typing import Sequence

from . import pulls, rulingwords, steps
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
        " about, the options and a 'How we got here' section, stop listing"
        " both, and report the number and the options to the owner on a card"
        " that has the section; the PR is offered for no fix, update or"
        " review round, and its other action lines wait",
    ),
    steps.Step.RULING_ESCALATES: (
        Marker.RULING_ESCALATES,
        "the Opus ruling escalated to the owner; label the PR and its ticket"
        " paused-owner with a comment of the options and a 'How we got here'"
        " section, stop listing both, and report the number and the options to"
        " the owner on a card that has the section; the PR is offered for"
        " no round",
    ),
}


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The line of a PR whose step asks for an Opus ruling or pauses it.

    Args:
        pull: the PR.

    Returns:
        One line, RULING DUE, PAUSE, RULING UNREADABLE or RULING
        ESCALATES, or none for any other step.
    """
    if pull.step.step is steps.Step.FIX_RULING:
        return [_unreadable(pull)]
    found = LINES.get(pull.step.step)
    if found is None:
        return []
    marker, action = found
    return [f"{marker.text} {pulls.reference(pull)}: {action}"]


def _unreadable(pull: pulls.PullFacts) -> str:
    where = pull.step.comment or "its newest Opus ruling comment"
    return (
        f"{Marker.RULING_UNREADABLE.text} {pulls.reference(pull)}: {where} is not"
        " in the ruling form: the second line must be 'Ruling: <word>', <word>"
        f" one of: {rulingwords.WORDS}; ask an agent to fix the comment (edit or"
        " repost); the PR is offered for no fix, update or review round until then"
    )
