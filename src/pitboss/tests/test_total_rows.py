"""The verdict's rows one at a time, at the edges the cells do not reach.

The keyword is total-routes, pitboss#444.
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import totalbody, totalchecks, totaljson, totalreview, totalverdict
from .knownkit import BASE, HEAD, change
from .says import says


def _first(action: str, pull: totaljson.JsonMap, ctx: totaljson.JsonMap) -> str:
    return next(iter(totalverdict.verdict(action, pull, ctx).lines), "")


class TestVerdict(unittest.TestCase):
    """Inputs not read, a response not of the schema, an action no row gates."""

    def test_444_every_input_is_required(self) -> None:
        """No input has a default."""
        assert_that(
            _first("merge", BASE.pull, {}), contains_string("input repo: not read")
        )

    def test_444_a_response_not_of_the_schema_stops(self) -> None:
        """A conclusion that is a list."""
        runs = [
            dict(each, conclusion=[5])
            for each in totaljson.records(BASE.ctx["check_runs"])
        ]
        world = change(ctx={"check_runs": runs})
        assert_that(
            _first("merge", world.pull, world.ctx),
            contains_string("not of GitHub's schema"),
        )

    def test_444_an_action_no_row_gates_goes(self) -> None:
        """``close`` has no review or check row."""
        assert_that(
            totalverdict.verdict("close", BASE.pull, BASE.ctx).word,
            equal_to(totalverdict.GO),
        )

    def test_444_a_label_pitboss_applies_leaves_the_review_current(self) -> None:
        """A ``labeled`` event of a known label after the review stops nothing."""
        world = change(events=[{"event": "labeled", "label": {"name": "dependencies"}}])
        assert_that(
            totalverdict.verdict("merge", world.pull, world.ctx).word,
            equal_to(totalverdict.GO),
        )


class TestBody(unittest.TestCase):
    """The body's rows and its kind."""

    def test_444_a_blocked_line_that_names_nothing(self) -> None:
        """It stops, saying so."""
        found = totalbody.body_findings(
            f"Fixes #1\n\nBlocked by the release\n\nHead: {HEAD}\n", HEAD, {}
        )
        says(" ".join(found), "names no item")

    def test_444_a_publish_branch(self) -> None:
        """Archives and their sums on a ``publish/`` branch are a publish."""
        files = [
            {"filename": "pkg/json_2026.11.1.0.bats"},
            {"filename": "pkg/json_2026.11.1.0.bats.sha256"},
        ]
        assert_that(
            totalbody.kind({"head": {"ref": "publish/json"}}, files),
            equal_to("publish"),
        )


class TestChecks(unittest.TestCase):
    """The newest run of each name."""

    def test_444_an_older_run_listed_later_is_not_current(self) -> None:
        """Order in the list does not decide; the start time does."""
        newer = {"name": "check", "id": 2, "started_at": "2026-11-02"}
        older = {"name": "check", "id": 1, "started_at": "2026-11-01"}
        assert_that(list(totalchecks.current_runs([newer, older])), equal_to([newer]))


class TestReview(unittest.TestCase):
    """The review's form, one fault at a time."""

    def test_444_the_faults(self) -> None:
        """No head line, a split verdict, a body with no Plan."""
        digest = totalreview.digest_of("")
        base = (
            f"Reviewed: {HEAD}\nPlan: approved\nExecution: approved\nVerdict:"
            f" approved\nBody: {digest}\n"
        )
        split = base.replace("Execution: approved", "Execution: changes needed")
        for text, said in (
            ("Verdict: approved\n", "0 head lines"),
            (split, "split verdict"),
        ):
            assert_that(
                totalreview.review_reading(text, HEAD, "", {}), contains_string(said)
            )
        said = [
            totalreview.plan_reading(base, plan)
            for plan in ("no plan here", "## Plan\n\nsteps\n")
        ]
        says(said[0], "`## Plan` section")
        says(said[1], "changed since the newest review")

    def test_444_lines_of_skips_blank_lines(self) -> None:
        """One value a line; a blank line is none."""
        assert_that(
            totaljson.lines_of('\n{"a": 1}\n\n[2, 3]\n'), equal_to([{"a": 1}, 2, 3])
        )
