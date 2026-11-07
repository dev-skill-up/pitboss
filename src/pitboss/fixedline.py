"""The FIXED ON BASE line: a red CI the base has passed (keyword: fixed-on-base).

A PR of a repository under ``[merge_queue] repositories`` whose head is red
only from checks that passed on the base after the head's run is not told to fix
the CI, nor to merge the base into its branch (pitboss#314): the queue tests it
on the base.
"""

from typing import Sequence

from . import basefix, pulls, steps
from .markers import Marker

ACTIONS = {
    steps.Step.MERGE: steps.ENQUEUE,
    steps.Step.REGULAR_REVIEW: steps.REQUEST_REVIEW,
}


def _passed(each: basefix.Answer) -> str:
    return (
        f"{each.failed.name} (job {each.failed.id}) failed at"
        f" {each.failed.completed_at}, passed on the base at"
        f" {each.passed.completed_at} (job {each.passed.id})"
    )


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The FIXED ON BASE line of a PR whose red CI the base has answered.

    Args:
        pull: the PR.

    Returns:
        The line, or none when no failed check of the head was answered, or
        the PR has a conflict (its line is ``CONFLICT``: the base is merged in
        only then).
    """
    if not pull.signals.fixed or pulls.conflicted(pull):
        return []
    said = "; ".join(_passed(each) for each in pull.signals.fixed)
    step = pull.step
    action = ACTIONS.get(step.step) or f"next step: {steps.describe(step)}"
    return [
        f"{Marker.FIXED_ON_BASE.text} {pulls.reference(pull)}: {said}; the red CI"
        f" is no work and {pull.pull.base} is not merged into"
        f" {pull.pull.head.branch}: {action}"
    ]
