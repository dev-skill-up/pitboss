"""A red check's brief prints its log and the rule on its cause (pitboss#420)."""

import unittest

from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import brief, causetext
from . import suggestions, world
from .briefmake import pinned, text
from .says import has_none
from .test_commands import sweep

SENTENCE = (
    "the answer to a red check is its cause: either the log names it (the step,"
    " the line) or the next change is the trace or state capture that would show"
    " it (a ticket or a change of its own); a push or a re-run whose only purpose"
    " is to get rid of a flake is refused (a re-run that works around a GitHub"
    " problem, such as a run stuck queued with no jobs, is not)"
)


def pr_three(check: object) -> world.World:
    """A world whose PR 3 has one check (PR 1 of the world is red).

    Args:
        check: the check run of PR 3's head.

    Returns:
        The world.
    """
    here = world.make_world()
    here.bodies.update(world.pull_bodies("owner/project", 3, [check], "clean"))
    return here


def matching(lines: Sequence[str], *words: str) -> Sequence[str]:
    """The lines that contain a word.

    Args:
        lines: the lines.
        *words: the words.

    Returns:
        The lines that contain any of the words.
    """
    return [each for each in lines if any(word in each for word in words)]


class TestCauseLine(unittest.TestCase):
    """The rule, and where a log is; the sweep says neither."""

    def test_the_rule_is_pinned(self) -> None:
        """The rule's words are the ones the ticket asks for."""
        assert_that(causetext.RULE, equal_to(SENTENCE))

    def test_a_green_check_prints_none_of_it(self) -> None:
        """PR 3, whose check passed, has no FAILED line, RED CAUSE line or rule."""
        lines = [
            x for x in sweep(pr_three(world.GREEN)).out.splitlines() if "project#3" in x
        ]
        assert_that(len(lines) > 0, equal_to(True))
        assert_that(matching(lines, "FAILED", "RED CAUSE", SENTENCE), equal_to([]))


class TestCauseBrief(unittest.TestCase):
    """The brief that fixes a red CI."""

    def test_the_fix_ci_brief_prints_the_rule(self) -> None:
        """FIX_CI states that the cause is the answer."""
        pinned(brief.Kind.FIX_CI, [SENTENCE])

    def test_every_other_brief_leaves_it_out(self) -> None:
        """No other brief prints the rule or a log."""
        for kind in set(brief.Kind) - {brief.Kind.FIX_CI}:
            has_none(text(kind), [SENTENCE, "Failed check log:"])

    def test_a_brief_with_no_failed_check_has_no_log_line(self) -> None:
        """A PR whose check passed gets a brief with no log line."""
        lines = suggestions.third(pr_three(world.GREEN))[1]
        assert_that(matching(lines, "Failed check"), equal_to([]))
