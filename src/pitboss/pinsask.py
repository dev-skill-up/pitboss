"""Asking the pins-check only where a review would be offered (pitboss#34)."""

from typing import Callable

from . import config, pinsreading, shapes, steps

Ask = Callable[[config.Repo, shapes.Pull], pinsreading.Reading]


def at_review(
    ask: Ask, repo: config.Repo, pull: shapes.Pull, step: steps.Move
) -> pinsreading.Reading:
    """Ask about a PR only where a review would be offered for it.

    Args:
        ask: the function that reads a PR.
        repo: the PR's repository.
        pull: the PR.
        step: the step the review flow gave it.

    Returns:
        Nothing unless the step is a review of a PR that is not a draft (a
        draft's review is of its Plan), else what ``ask`` says.
    """
    if not steps.step_is(step, {steps.Step.REGULAR_REVIEW}) or pull.draft:
        return pinsreading.NOTHING
    return ask(repo, pull)


def unreviewed(step: steps.Move, reading: pinsreading.Reading) -> steps.Move:
    """The merge, when the pins-check printed OK, in place of the review.

    Args:
        step: the step the review flow gave the PR.
        reading: what the pins-check said.

    Returns:
        The merge step for OK, else the step.
    """
    return steps.merge() if pinsreading.cleared(reading) else step
