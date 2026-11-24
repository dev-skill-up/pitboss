"""The table of the steps that follow each ruling (keyword: ruling-after).

A PR held at PLAN EDITED is given the step of a ruling no review follows
(pitboss#475), as one that is not held is.
"""

from typing import Mapping, Sequence

from . import workerselect
from . import rulingwords, steps

# What follows each ruling but ``EXECUTION_IS_APPROVED``: the worker's round. The
# review after it is the ordinary review gate's, for the head and body the worker
# handed back (keyword: standing).
AS_RULED = (
    rulingwords.Ruling.SPLIT,
    rulingwords.Ruling.RESHAPE,
    rulingwords.Ruling.ABANDON,
)
AFTER: Mapping[rulingwords.Ruling, Sequence[steps.Next]] = {
    rulingwords.Ruling.DO_THESE_STEPS: (workerselect.worker(steps.Task.RULING_STEPS),),
    rulingwords.Ruling.REVISE_THE_PLAN: (workerselect.worker(steps.Task.REVISE_PLAN),),
    rulingwords.Ruling.ESCALATE: (steps.ruling_escalates(),),
    **dict.fromkeys(AS_RULED, (workerselect.worker(steps.Task.RULING_AS_GIVEN),)),
}


def held_step(held: steps.Next, ruled: rulingwords.Ruling | None) -> steps.Next:
    """The step of a held PR: its ruling's own when one is due (pitboss#475).

    A Plan edited with no ``revise the plan`` ruling holds the PR, but a readable
    ruling that no review and no push has followed is Opus's word on what to do
    next, so its step is offered and the Plan is read again once it is applied.
    ``execution is approved`` is not one: it merges, and an edited Plan stays held.

    Args:
        held: the step of the hold (``flowstate.ruling_hold``).
        ruled: the ruling no review or push has followed, None when none.

    Returns:
        The first step of the ruling's row of ``AFTER`` when the hold is a Plan
        edited and such a ruling is due; else the hold.
    """
    due = AFTER.get(ruled) if ruled else None
    return due[0] if due and held.step is steps.Step.PLAN_EDITED else held
