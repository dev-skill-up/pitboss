"""An approval of a head waits for its green check run.

The keyword is approval-ci, quire#1038.
"""

import json
import unittest
from typing import Mapping

from hamcrest import assert_that, equal_to

from .. import approvalci
from . import world
from .says import exits, says

HEAD = "a" * 40


def review(verdict: str) -> str:
    """A review comment in the default form.

    Args:
        verdict: the verdict word.

    Returns:
        Its text.
    """
    return (
        f"## Review\n\nReviewed: {HEAD}\nVerdict: {verdict}\n"
        f"Plan: {verdict}\nExecution: {verdict}\n"
    )


def lint(verdict: str, runs: object) -> world.Result:
    """Run ``lint review`` with a review and check runs.

    Args:
        verdict: the verdict word.
        runs: the ``check_runs`` list.

    Returns:
        What the command did.
    """
    here = world.make_world()
    comment, listed = here.workspace / "review.md", here.workspace / "runs.json"
    comment.write_text(review(verdict), encoding="utf-8")
    listed.write_text(json.dumps({"check_runs": runs}), encoding="utf-8")
    argv = ["lint", "review", str(comment), "--head", HEAD, "--config", here.config]
    return world.invoke(here, *argv, "--check-runs", str(listed))


def run(
    status: str, conclusion: str | None, name: str = "check"
) -> Mapping[str, object]:
    """A check run as GitHub gives it.

    Args:
        status: its status.
        conclusion: its conclusion.
        name: its name.

    Returns:
        The run.
    """
    return {"name": name, "status": status, "conclusion": conclusion, "started_at": "t"}


class TestApprovalCi(unittest.TestCase):
    """The four cases of quire#1038."""

    def test_t55_an_approval_with_no_run_is_refused(self) -> None:
        """No run of the check."""
        done = lint("approved", [run("completed", "success", name="other")])
        exits(done, 1)
        says(done.out, "waiting for CI")

    def test_t55_an_approval_with_a_run_in_progress_is_refused(self) -> None:
        """Not completed."""
        done = lint("approved", [run("in_progress", None)])
        exits(done, 1)
        says(done.out, "not completed")

    def test_t55_an_approval_with_a_failed_run_is_refused(self) -> None:
        """Completed, not success."""
        done = lint("approved", [run("completed", "failure")])
        exits(done, 1)
        says(done.out, "concluded failure")

    def test_t55_a_green_run_and_a_changes_needed_review_pass(self) -> None:
        """Completed and green; and a review that does not approve."""
        green = lint("approved", [run("completed", "success")])
        needs = lint("changes needed", [run("in_progress", None)])
        assert_that((green.code, needs.code), equal_to((0, 0)))

    def test_t55_the_newest_run_decides(self) -> None:
        """An older red run does not count."""
        older = {**run("completed", "failure"), "started_at": "a"}
        newer = {**run("completed", "success"), "started_at": "b"}
        exits(lint("approved", [older, newer]), 0)
        assert_that(approvalci.ARGUMENTS[0] is approvalci.RUNS_ARGUMENT, equal_to(True))

    def test_t55_a_runs_file_with_no_list_is_an_error(self) -> None:
        """The file is not the JSON of check runs."""
        with self.assertRaises(ValueError):
            lint("approved", "not a list")
