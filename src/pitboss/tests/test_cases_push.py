"""I27 and I11 of pitboss#444: a push that moves the head says the Evidence is stale."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import expansion
from . import fakes, world
from .linting import OK
from .test_push_draft import PULLS, gits, held_world, pushed

COMMAND = "nox -s tests"
EVIDENCE = "## Evidence\n\n" + expansion.block(COMMAND, OK, "a" * 40)
STALE = "EVIDENCE STALE: re-run uvx pitboss expand"


class TestPushStale(unittest.TestCase):
    """The line after the push, for a PR with expanded Evidence."""

    def test_i27_a_push_with_expanded_evidence_prints_the_stale_line(self) -> None:
        """The PR's body has an expand block: the line is printed after `pushed`."""
        here = held_world([{"draft": True, "body": EVIDENCE}], "branch-1")
        result = pushed(here)
        assert_that(result.out, contains_string("pushed\n" + STALE))

    def test_i27_a_pr_with_no_evidence_prints_nothing(self) -> None:
        """The nearest input that must stay silent."""
        here = held_world([{"draft": True, "body": "Fixes #1\n"}], "branch-1")
        result = pushed(here)
        assert_that(STALE not in result.out, "no line")
        assert_that(PULLS.format(branch="branch-1") in here.bodies, "the PR was listed")


def changed(here: world.World) -> world.World:
    """Give branch-1 a commit that changes a file against the base.

    Args:
        here: the world.

    Returns:
        The world.
    """
    fakes.run_git(here.clone, "checkout", "--quiet", "branch-1")
    (here.clone / "changed.txt").write_text("x\n", encoding="utf-8")
    fakes.run_git(here.clone, "add", "changed.txt")
    fakes.run_git(here.clone, "commit", "--quiet", "-m", "change")
    return here


class TestPushExecution(unittest.TestCase):
    """I11: a body that lost its Execution section stops the push."""

    def test_i11_a_body_with_no_execution_refuses_the_push(self) -> None:
        """The branch changes files against the base; the body has no Execution."""
        body = "Fixes #1\n\n## Plan\nthe plan\n"
        here = changed(held_world([{"draft": True, "body": body}], "branch-1"))
        result = pushed(here)
        assert_that(result.code, equal_to(1))
        assert_that(result.out, contains_string("execution-section"))
        assert_that(gits(here), equal_to(0))

    def test_i11_a_body_with_its_execution_is_pushed(self) -> None:
        """The nearest input that must pass."""
        body = "Fixes #1\n\n## Plan\nthe plan\n\n## Execution\nx\n"
        here = changed(held_world([{"draft": True, "body": body}], "branch-1"))
        assert_that(pushed(here).code, equal_to(0))
