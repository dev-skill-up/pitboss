"""A PR as read, for the tests of the decider (plan 6.1: the flow's rows are decide's).

``decide.facts_of`` runs the review flow on what was read, so a record a test
makes holds the flow's inputs: a state whose step the test names.
"""

import dataclasses

from .. import witnessread
from . import test_flow

read_of = witnessread.read_of
APPROVED = test_flow.graded(test_flow.APPROVED, test_flow.APPROVED, 1)
PLAN_ONLY = dataclasses.replace(APPROVED, execution=None)  # its Plan approved alone
# a green PR whose Plan and Execution are approved: the merge step
MERGING = test_flow.state(APPROVED)
# an approved PR whose CI runs: the wait for the CI
RUNNING = test_flow.state(APPROVED, checks=(test_flow.RUNNING,))
# a draft whose Plan is approved, with the runners clear: the undraft step
UNDRAFTING = test_flow.state(PLAN_ONLY, checks=(), draft=True, undraft_clear=True)
