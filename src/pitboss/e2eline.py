"""The line of a draft whose changed e2e suite has run nowhere (keyword: run-e2e).

A draft's CI runs plan and build only, so a PR that changes what the e2e suite
runs on has no e2e result until the check workflow is dispatched on its branch
(pitboss#199: an approval and an owner's ruling were given on a PR whose e2e
was red). A draft's own run, complete or not, skipped e2e, so only a completed
dispatched run of the head ends the step. The line is the step ``slots next`` prints for the PR, in the same
words, and it replaces ``WAIT-FOR-CI`` for it.
"""

from typing import Sequence

from . import pulls, steps


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The RUN E2E BEFORE APPROVAL line of a PR at that step.

    Args:
        pull: the PR.

    Returns:
        The line, none when the PR's step is another.
    """
    if pull.step.step is not steps.Step.RUN_E2E:
        return []
    return [
        f"{steps.describe(pull.step)} ({pulls.reference(pull)}); a draft's CI skips"
        " e2e, so no review approves it until the dispatched run of its head has"
        " completed"
    ]
