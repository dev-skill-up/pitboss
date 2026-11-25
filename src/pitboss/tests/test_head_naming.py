"""A Plan that names the head, and a red head the base passes (quire#1125, #1128)."""

import dataclasses
import unittest

from hamcrest import assert_that, equal_to

from .. import basefix, expansion, gaterows, plannaming, pullrecords, shapes
from .. import totalchecks
from . import gatestate
from ..gatestop import Route
from . import test_flow

OLD = "9aef3c62038ab7ef543819706f30bf65860565d3"
NEW = "012bdd6f570104c3d480873d96b15b971c234508"
PLAN = "## Plan\n\n1. Evidence: `commits/{}/status` prints `success`."


def recorded() -> str:
    """The digest a review records of the Plan that named the old head.

    Returns:
        The digest.
    """
    return expansion.section_digest(PLAN.format(OLD))


class TestPlanNamesHead(unittest.TestCase):
    """``plannaming.current``."""

    def test_a_push_that_only_moves_the_head_in_the_plan_is_no_edit(self) -> None:
        """Current at the new head; words edited at the same head are not.

        A review that wrote its whole head puts it back in the Plan, so the
        words are compared; one that kept eight digits cannot be rebuilt.
        """
        now = PLAN.format(NEW)
        same = PLAN.format(OLD).replace("prints", "shows")
        quiet = PLAN.replace("{}", "x")
        edited = now.replace("prints", "shows")
        found = [
            plannaming.current(recorded(), now, OLD[:8], NEW),
            plannaming.current(recorded(), same, OLD[:8], OLD),
            plannaming.current(recorded(), PLAN.format(OLD), OLD[:8], OLD),
            plannaming.current(recorded(), quiet, OLD[:8], NEW),
            plannaming.current(recorded(), now, OLD, NEW),
            plannaming.current(recorded(), edited, OLD, NEW),
        ]
        assert_that(found, equal_to([True, False, True, False, True, False]))


class TestRedHeadIsFixed(unittest.TestCase):
    """``basefix.settle_approved``."""

    def test_only_an_approved_pr_is_settled(self) -> None:
        """The checks stay red with no approval, and are settled with one."""
        red = dataclasses.replace(test_flow.RED, id=5)
        passed = dataclasses.replace(
            test_flow.RED, id=6, failed=False, succeeded=True, finished=True
        )
        answer = basefix.Answer(failed=red, passed=passed)
        yes = test_flow.APPROVED
        approved = [test_flow.graded(yes, yes, 1)]
        rejected = [test_flow.graded(shapes.Verdict.CHANGES_NEEDED, None, 1)]
        found = [
            [each.failed for each in basefix.settle_approved([red], [answer], graded)]
            for graded in (approved, rejected, [])
        ]
        assert_that(found, equal_to([[False], [True], [True]]))


def status(context: str, state: str, said: str) -> pullrecords.Status:
    """A commit status of the head.

    Args:
        context: its name.
        state: its state.
        said: its description.

    Returns:
        The status.
    """
    return pullrecords.Status(context=context, state=state, description=said)


class TestReviewStatus(unittest.TestCase):
    """A failed status about the newest review is the review's stop (quire#1130)."""

    def test_only_a_failed_status_that_speaks_of_the_review_is_one(self) -> None:
        """Failed and ``review:``; a pass, a wait, another text or a read are not."""
        said = 'review: it names a race and has no line "Race check: ..."'
        statuses = [
            status("guidelines-lint", "failure", said),
            status("guidelines-lint", "success", said),
            status("guidelines-lint", "pending", said),
            status("guidelines-lint", "failure", "diff: a file"),
            status("pitboss-gate", "failure", said),
        ]
        found = totalchecks.review_status_lines("merge", statuses)
        wanted = [f"status guidelines-lint=failure: {said}"]
        assert_that(list(found), equal_to(wanted))
        assert_that(totalchecks.review_status_lines("close", statuses), equal_to([]))

    def test_the_stop_is_the_reviews_unless_a_check_is_red(self) -> None:
        """The review route carries ``act review``; a red check comes first."""
        review = status("guidelines-lint", "failure", "review: no Race line")
        other = status("lint", "failure", "diff: a file")
        found = []
        for statuses in ([review], [review, other]):
            reads = gatestate.lists_of(statuses=statuses)
            stops = gaterows.check_stops("merge", gatestate.state(reads=reads))
            found.append([each.route for each in stops])
        red = totalchecks.check_stops("merge", [], [review], set())
        wanted = [[Route.REVIEW], [Route.RED, Route.REVIEW]]
        assert_that((found, red), equal_to((wanted, [])))
