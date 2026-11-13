"""A PR as read, for the tests of the decider (plan 6.1: the flow's rows are decide's).

``decide.facts_of`` runs the review flow on what was read, so a record a test
makes holds the flow's inputs: a state whose step the test names.
"""

import dataclasses

from .. import flowstate, pullfacts, pullobject, totalschema
from . import test_flow

# the PR object a test's gate reads when it reads none
NO_OBJECT = pullobject.pull_object({}, totalschema.schema())
APPROVED = test_flow.graded(test_flow.APPROVED, test_flow.APPROVED, 1)
PLAN_ONLY = dataclasses.replace(APPROVED, execution=None)  # its Plan approved alone
# a green PR whose Plan and Execution are approved: the merge step
MERGING = test_flow.state(APPROVED)
# an approved PR whose CI runs: the wait for the CI
RUNNING = test_flow.state(APPROVED, checks=(test_flow.RUNNING,))
# a draft whose Plan is approved, with the runners clear: the undraft step
UNDRAFTING = test_flow.state(PLAN_ONLY, checks=(), draft=True, undraft_clear=True)


def read_of(
    facts: pullfacts.PullFacts, state: flowstate.PullState
) -> pullfacts.PullRead:
    """A PR as read: its facts, less the step, and the flow's state.

    Args:
        facts: what a test says of the PR (its step is not read).
        state: what the review flow's rows ask of it.

    Returns:
        The PR as read.
    """
    return pullfacts.PullRead(
        repo=facts.repo,
        pull=facts.pull,
        checks=facts.checks,
        review=facts.review,
        standing=facts.standing,
        signals=facts.signals,
        unreadable=facts.unreadable,
        review_rounds=facts.review_rounds,
        state=state,
        posted=pullfacts.Posted(object=NO_OBJECT, statuses=()),
    )
