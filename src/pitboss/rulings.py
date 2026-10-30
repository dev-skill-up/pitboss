"""What follows an Opus ruling (keyword: review-flow).

The ruling is a PR comment whose first line is ``Opus ruling`` and whose second
is ``Ruling:`` and one of the words of ``Ruling``. It is taken as given.
"""

import enum
from typing import Mapping, Sequence

from . import flow, sessionurl, steps

RULING_LINE_PREFIX = "Ruling: "


class Ruling(enum.Enum):
    """What an Opus ruling rules; the value is the word on its ``Ruling:`` line.

    Attributes:
        DO_THESE_STEPS: a worker does exactly the steps it lists.
        REVISE_THE_PLAN: the plan is revised.
        EXECUTION_IS_APPROVED: the execution is approved.
        SPLIT: the ticket and PR are split.
        RESHAPE: the ticket and PR are reshaped.
        ABANDON: the ticket and PR are abandoned.
        ESCALATE: the owner decides.
    """

    DO_THESE_STEPS = "do these steps"
    REVISE_THE_PLAN = "revise the plan"
    EXECUTION_IS_APPROVED = "execution is approved"
    SPLIT = "split"
    RESHAPE = "reshape"
    ABANDON = "abandon"
    ESCALATE = "escalate to the owner"


_RULINGS = {each.value: each for each in Ruling}


def read_ruling(body: str) -> Ruling | None:
    """Read what a ruling comment rules from its second line.

    Args:
        body: the comment (first line ``Opus ruling``, second line
            ``Ruling:`` and one of the words of ``Ruling``).

    Returns:
        The ruling, or None when the comment is none or says no known word.
    """
    lines = sessionurl.lines(body)
    if not flow.is_ruling(body) or len(lines) < 2:
        return None
    second = lines[1].rstrip()
    if not second.startswith(RULING_LINE_PREFIX):
        return None
    return _RULINGS.get(second[len(RULING_LINE_PREFIX) :])


AS_RULED = (Ruling.SPLIT, Ruling.RESHAPE, Ruling.ABANDON)
AFTER: Mapping[Ruling, Sequence[steps.Next]] = {
    Ruling.DO_THESE_STEPS: (
        steps.worker(steps.Task.RULING_STEPS),
        steps.regular_review(steps.Stage.RULING_STEPS),
    ),
    Ruling.REVISE_THE_PLAN: (
        steps.worker(steps.Task.REVISE_PLAN),
        steps.regular_review(steps.Stage.PLAN_ONLY),
    ),
    Ruling.ESCALATE: (steps.pause_for_owner(),),
    **dict.fromkeys(AS_RULED, (steps.worker(steps.Task.RULING_AS_GIVEN),)),
}


def after_opus_ruling(pr: flow.PullState, ruling: Ruling) -> Sequence[steps.Next]:
    """The steps that follow a recorded ruling; the ruling is taken as given.

    A split, reshape or abandon is carried out as ruled and is not checked
    against the one-ticket-one-PR rules.

    Args:
        pr: the PR.
        ruling: what the ruling rules.

    Returns:
        The steps, in order.
    """
    if ruling is Ruling.EXECUTION_IS_APPROVED:
        return (merge_when_green(pr),)
    return AFTER[ruling]


def merge_when_green(pr: flow.PullState) -> steps.Next:
    """Merge when the checks of the head are green; else what the gate says.

    Args:
        pr: the PR.

    Returns:
        The step.
    """
    ci = flow.ci_result(pr)
    if ci is None:
        return steps.wait_for_ci()
    return steps.merge() if ci is flow.Ci.GREEN else steps.worker(steps.Task.FIX_CI)
