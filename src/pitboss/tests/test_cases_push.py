"""I27 and I11 of pitboss#444: a push that moves the head says the Evidence is stale."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import expansion
from . import fakes, repositories, world
from .linting import OK
from .test_push_draft import PULLS, gits, held_world, pushed

COMMAND = "nox -s tests"
EVIDENCE = "## Evidence\n\n" + expansion.block(COMMAND, OK, "a" * 40)
STALE = "EVIDENCE STALE: re-run uvx pitboss expand"


def with_body(body: str) -> world.World:
    """The draft PR of branch-1 whose body is given, held for a push.

    Args:
        body: the PR's body.

    Returns:
        The world.
    """
    return held_world([{"draft": True, "body": body}], "branch-1")


def changed(here: world.World) -> world.World:
    """Give branch-1 a commit that changes a file against the base.

    Args:
        here: the world.

    Returns:
        The world.
    """
    switch = ("checkout", "--quiet", "branch-1")
    fakes.run_git(here.clone, *switch)
    repositories.commit_file(here.clone, "changed.txt")
    return here


class TestPushStale(unittest.TestCase):
    """The line after the push, for a PR with expanded Evidence."""

    def test_i27_a_push_with_expanded_evidence_prints_the_stale_line(self) -> None:
        """The PR's body has an expand block: the line is printed after `pushed`."""
        assert_that(
            pushed(with_body(EVIDENCE)).out, contains_string("pushed\n" + STALE)
        )

    def test_i27_a_pr_with_no_evidence_prints_nothing(self) -> None:
        """The nearest input that must stay silent."""
        here = with_body("Fixes #1\n")
        result = pushed(here)
        listed = PULLS.format(branch="branch-1") in here.bodies
        assert_that((STALE in result.out, listed), equal_to((False, True)))


class TestPushExecution(unittest.TestCase):
    """I11: a body that lost its Execution section stops the push."""

    def test_i11_a_body_with_no_execution_refuses_the_push(self) -> None:
        """The branch changes files against the base; the body has no Execution."""
        here = changed(with_body("Fixes #1\n\n## Plan\nthe plan\n"))
        result = pushed(here)
        said = (result.code, "execution-section" in result.out, gits(here))
        assert_that(said, equal_to((1, True, 0)))

    def test_i11_a_base_git_cannot_diff_against_is_no_change(self) -> None:
        """A PR into a branch the clone lacks: nothing to compare, the push goes."""
        listed = [{"draft": True, "body": "Fixes #1\n", "base": {"ref": "nowhere"}}]
        here = changed(held_world(listed, "branch-1"))
        assert_that(pushed(here).code, equal_to(0))

    def test_i11_a_body_with_its_execution_is_pushed(self) -> None:
        """The nearest input that must pass."""
        body = "Fixes #1\n\n## Plan\nthe plan\n\n## Execution\nx\n"
        assert_that(pushed(changed(with_body(body))).code, equal_to(0))
