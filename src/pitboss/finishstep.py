"""The step that finishes a PR handed back unfinished (keyword: finish-partial).

``finishpartial`` says why such a PR exists and names a stranded one for the sweep;
``decide`` gives the PR the step this module says (the one-path plan, 6.1: the
settlers are rows of ``decide``).
"""

from typing import Sequence

from . import pullfacts, steps, textlint

# the steps that merge or review a PR whose body the lint refuses
GATED = {
    steps.Step.REGULAR_REVIEW,
    steps.Step.UNDRAFT,
    steps.Step.MERGE,
}
NO_CHECK = (
    "no clean Plan check covers the Plan at this head: post `uvx pitboss plan-check`"
)
RED_BODY = "the `text-lint` status of the head is red ({description}): fix the body"


def reasons(pull: pullfacts.PullFacts) -> Sequence[str]:
    """What is missing from a PR, from its step and the statuses of its head.

    Args:
        pull: the PR.

    Returns:
        The reasons, none when the PR is not partial.
    """
    step = steps.step_of(pull.step)
    found = []
    if step is steps.Step.PLAN_CHECK:
        found.append(NO_CHECK)
    if step in {steps.Step.PLAN_CHECK} | GATED:
        found += [
            RED_BODY.format(description=each.description or each.state)
            for each in pull.signals.statuses
            if each.context == textlint.CONTEXT and each.state in textlint.RED
        ]
    return found


def step_of(pull: pullfacts.PullFacts) -> steps.Next | None:
    """The step that finishes a partial PR.

    Args:
        pull: the PR, at the step its own facts and closure give.

    Returns:
        ``FINISH_PARTIAL`` with what is missing; None when the PR is not partial.
    """
    found = reasons(pull)
    if not found:
        return None
    why = "; ".join(found)
    return steps.Next(
        step=steps.Step.WORKER,
        task=steps.Task.FINISH_PARTIAL,
        findings=why,
        reason=f": {why}",
    )
