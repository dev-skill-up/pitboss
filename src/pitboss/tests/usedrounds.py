"""The round a rejection after a used ruling is (keyword: ruling-typed, #517)."""

from hamcrest import assert_that, equal_to

from .. import flow, flowstate, steps

PLAN_ROUND = steps.worker(steps.Task.REVISE_PLAN)


def expect_execution_round(pr: flow.PullState) -> None:
    """Assert the PR is at the fix of its Execution against its newest ruling.

    Args:
        pr: the PR.
    """
    want = steps.worker(steps.Task.FIX_EXECUTION, flowstate.ruling_address(pr))
    assert_that(flow.next_step(pr), equal_to(want))
