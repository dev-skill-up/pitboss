"""What follows an Opus ruling (keyword: review-flow).

The ruling is a PR comment whose first line is ``Opus ruling`` and whose second
is ``Ruling:`` and one of the words of ``Ruling`` (``rulingwords``). It is taken
as given. The flow reads the table ``AFTER`` (``flow.AFTER``);
``after_opus_ruling`` follows it.
"""

from typing import Sequence

from . import conflicts, flow, rulingafter, rulingwords, steps

RULING_LINE_PREFIX = rulingwords.RULING_LINE_PREFIX
Ruling = rulingwords.Ruling
read_ruling = flow.read_ruling
AS_RULED = rulingafter.AS_RULED
AFTER = flow.AFTER


def after_opus_ruling(pr: flow.PullState, ruling: Ruling) -> Sequence[steps.Move]:
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


def merge_when_green(pr: flow.PullState) -> steps.Move:
    """Merge when the checks of the head are green and there is no conflict.

    Else what the gate says: wait for CI, fix a red CI, resolve the conflict.

    Args:
        pr: the PR.

    Returns:
        The step.
    """
    ci = flow.ci_result(pr)
    if ci is None:
        return steps.IDLE
    green = ci is flow.Ci.GREEN
    return (
        conflicts.merge_unless_conflict(pr)
        if green
        else steps.worker(steps.Task.FIX_CI)
    )
