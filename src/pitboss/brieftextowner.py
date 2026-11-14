"""The sentences about what the owner can do and what a worker did (pitboss#352).

Like those of ``brieftext``, they are pinned by tests, so a change to them is a
reviewed code change. ``OWNER`` is in the worker briefs, the review briefs and
the sweep's reminders; ``WORKER_ACTIONS`` is in the sweep's reminders.
"""

from . import brieftextrules

OWNER = (
    "Owner: a ticket, brief, plan or review never states what the owner cannot or"
    " will not do, or that something is outside his reach, unless the sentence"
    " quotes his own words and their date; without a quote the step is asked of"
    " him as a request in the hand-back, never assumed impossible."
)
WORKER_ACTIONS = (
    "Worker actions: a statement about what a worker did is made from the output"
    " of `pitboss worker-actions WORKER_OUTPUT PATTERN...`; its `no match in N"
    ' calls and the final report` is reported with its count, never as "it did'
    ' not"; an unexplained action by the shared `moshez` account is ours until'
    " that command shows otherwise, and is never attributed to the owner"
    " (pitboss#352)."
)
REMINDERS = (OWNER, WORKER_ACTIONS, *brieftextrules.REMINDERS)
