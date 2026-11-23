"""An impossibility the orchestrator accepts after an Opus ruling pauses the PR.

The keyword is impossible-after-ruling. The owner, 2026-11-17: a worker's
impossibility still has to pass the orchestrator's judgment of its evidence; once
it does, on a PR that already has its Opus ruling, ``pitboss impossible`` puts
the ``paused-owner`` label and posts the question, and nothing waits.
"""

import re
from typing import Sequence

from . import analysis, flowstate, handbackform, impossiblecites, partial, steps

IMPOSSIBLE = re.compile(handbackform.IMPOSSIBLE.pattern, re.MULTILINE)
OPTIONS = (
    "Options:\n"
    "1. Reword or drop the Done-when item the hand-back shows impossible.\n"
    "2. Close the ticket.\n"
)
NO_IMPOSSIBILITY = (
    "the hand-back shows no impossibility: an `impossible` line of the hand-back"
    " form, or `Impossible: <cmd> -> <output>`"
)
PAUSED = "the PR is already paused for the owner"
NO_RULING = (
    "the PR has no Opus ruling yet, so the Opus judge is not used up: the next step"
    " is the Opus ruling brief (`pitboss slots next`), not the owner"
)
QUESTION = (
    "Owner pause: a worker handed back an impossibility after the Opus ruling.\n\n"
    "{options}\n## {section}\n\nThe PR has its Opus ruling and the worker's hand-back"
    " shows an item that cannot be met:\n\n{handback}\n"
)


def shows_impossibility(handback: str) -> bool:
    """Whether a hand-back shows an item that cannot be met.

    Args:
        handback: the hand-back text.

    Returns:
        True for an ``impossible`` line of the hand-back form or an
        ``Impossible: <cmd> -> <output>`` line.
    """
    return bool(IMPOSSIBLE.search(handback) or partial.IMPOSSIBLE.search(handback))


def refusal(
    handback: str,
    comments: Sequence[str],
    labels: Sequence[str],
    register: Sequence[str],
) -> str:
    """Say why a hand-back may not pause a PR for the owner.

    Args:
        handback: the hand-back text.
        comments: the texts of the PR's comments.
        labels: the PR's labels.
        register: the words of each rule of the register of the owner's rules.

    Returns:
        The reason; empty when the hand-back shows an impossibility, the PR has an
        Opus ruling, is not yet paused for the owner and the hand-back cites the
        rulings in their exact words (``impossiblecites``).
    """
    if not shows_impossibility(handback):
        return NO_IMPOSSIBILITY
    if steps.PAUSED_LABEL in labels:
        return PAUSED
    rulings = [each for each in comments if flowstate.is_ruling(each)]
    if not rulings:
        return NO_RULING
    return impossiblecites.refusal(handback, register, rulings)


def question(handback: str) -> str:
    """The question the owner is asked.

    Args:
        handback: the hand-back text.

    Returns:
        The text for ``owner-pause``: the options and the ``How we got here``
        section holding the hand-back.
    """
    return QUESTION.format(
        options=OPTIONS, section=analysis.SECTION, handback=handback.strip()
    )
