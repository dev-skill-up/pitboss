"""The sentence of the review briefs about notes (pitboss#240).

Like those of ``brieftext``, it is pinned by a test, so a change to it is a
reviewed code change.
"""

from . import brieftextci, brieftextexec

REVIEW_NOTES = (
    "Notes: a gap against the goal or the Done-when that you can name (a case, a"
    " fixture, a repository kind the change does not handle) is a finding, never"
    " a note; a note holds only what the change did not cause."
)
DEVIATIONS_REVIEW = (
    "Deviations: read the PR body's `Deviations:` line. A listed edit by shell is"
    " a finding only when it left a trace in the tree that the Edit tool would"
    " not have (a stray or backup file, a changed mode or line ending, a file"
    " removed that the change does not remove); it never fails a PR for a clean"
    " tree. Record each listed deviation, finding or not, on a line of the"
    " comment that starts with `Deviation:`, for the sweep's ledger line for the"
    " worker (pitboss#257)."
)
# the sentences of the reviews that grade an Execution
EXECUTION_REVIEW = (
    brieftextexec.PLAN_COMMANDS_EXECUTION,
    brieftextci.REVIEW_CI_ACCEPTED,
    REVIEW_NOTES,
    DEVIATIONS_REVIEW,
)
