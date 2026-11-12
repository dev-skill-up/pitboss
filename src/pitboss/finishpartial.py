"""A PR a worker handed back unfinished is finished, in order (keyword: finish-partial).

quire#1119 was handed back partial (the worker was out of budget): its body failed
the lint, no Plan check was posted and the head was ahead of nothing. The flow gave
it ``PLAN_CHECK``, a step the NEXT list does not offer (it was written for the
worker that just pushed and still holds its slot), so the PR fell out of the order
and nobody finished it. Post-mortem: the plan and the audit of pitboss#444 proved
that every state prints a step, not that every step is *offered* to someone; the
states in which a PR is neither done nor offered are derived here from the steps:

* ``PLAN_CHECK`` (no clean Plan check covers the Plan at this head: a PR with no
  check, or a head ahead of the checked one, or a worker's hand-back that stopped
  before the check): a worker posts it. ``SEND_BACK_PLAN_CHECK`` (the check refused
  the Plan) stays the pushing worker's to send back (pitboss#471, offered as no
  round), so the sweep names it ``NO STEP`` instead;
* any step that merges or reviews while the ``text-lint`` status of the head is red
  (the body fails ``lint pr-body``): a PR so red cannot merge or be reviewed;
* a draft with a pushed head and no worker, a ledger slot released with work
  unfinished and a hand-back-check refusal are these states: the ledger is read
  only to hold a PR (``SLOT HELD``), so a PR whose slot is free is offered.

Such a PR is offered ``FINISH_PARTIAL`` (resume the same PR; it is a PR that needs
work, so ``work`` orders it by age ahead of the new tickets). ``stranded`` is the
sweep's line for a PR that is offered for nothing and waits for nobody.
"""

import dataclasses
from typing import Sequence

from . import pulls, steps, textlint, work

PREFIX = "FINISH PARTIAL"
STRANDED = "NO STEP"
# the steps a worker still holding the PR does: offered to nobody (a refused check is
# sent back by the worker that pushed, pitboss#471, so it is named, never offered)
UNOFFERED = {steps.Step.PLAN_CHECK, steps.Step.SEND_BACK_PLAN_CHECK}
# the steps that merge or review a PR whose body the lint refuses
GATED = {
    steps.Step.REGULAR_REVIEW,
    steps.Step.UNDRAFT,
    steps.Step.WAIT_FOR_UNDRAFT,
    steps.Step.WAIT_FOR_CI,
    steps.Step.MERGE,
}
NO_CHECK = (
    "no clean Plan check covers the Plan at this head: post `uvx pitboss plan-check`"
)
RED_BODY = "the `text-lint` status of the head is red ({description}): fix the body"


def reasons(pull: pulls.PullFacts) -> Sequence[str]:
    """What is missing from a PR, from its step and the statuses of its head.

    Args:
        pull: the PR.

    Returns:
        The reasons, none when the PR is not partial.
    """
    step = pull.step
    found = []
    if step.step is steps.Step.PLAN_CHECK:
        found.append(NO_CHECK)
    if step.step in {steps.Step.PLAN_CHECK} | GATED:
        found += [
            RED_BODY.format(description=each.description or each.state)
            for each in pull.signals.statuses
            if each.context == textlint.CONTEXT and each.state in textlint.RED
        ]
    return found


def _finished(read: pulls.Read) -> tuple[pulls.Read, str]:
    if not isinstance(read, pulls.PullFacts):
        return read, ""
    found = reasons(read)
    if not found:
        return read, ""
    why = "; ".join(found)
    step = steps.Next(
        step=steps.Step.WORKER,
        task=steps.Task.FINISH_PARTIAL,
        findings=why,
        reason=f": {why}",
    )
    finished = dataclasses.replace(read, step=step)
    return finished, f"{PREFIX} {pulls.reference(read)}: {step.findings}"


def settle(reads: Sequence[pulls.Read]) -> tuple[Sequence[pulls.Read], Sequence[str]]:
    """Give each partial PR the step that finishes it.

    Args:
        reads: every open PR.

    Returns:
        The PRs, and the sweep's line for each that was changed.
    """
    done = [_finished(each) for each in reads]
    return [each for each, _ in done], [line for _, line in done if line]


def stranded(reads: Sequence[pulls.Read]) -> Sequence[str]:
    """The sweep's line for each PR that is offered for nothing and waits for nobody.

    Args:
        reads: every open PR, after ``settle``.

    Returns:
        One line each, naming the PR and its step; none while every PR has a step.
    """
    return [
        f"{STRANDED} {pulls.reference(each)}: {steps.describe(each.step)}"
        for each in pulls.readable(reads)
        if each.step.step in UNOFFERED and work.category_of(each) is None
    ]
