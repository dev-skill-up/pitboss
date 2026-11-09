"""A red check prints its log and the rule on its cause (pitboss#420)."""

import dataclasses
import unittest

from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, causeline, causetext, shapes
from . import suggestions, world
from .briefmake import has_none, make, pinned, text
from .test_commands import sweep

SENTENCE = (
    "the answer to a red check is its cause: either the log names it (the step,"
    " the line) or the next change is the trace or state capture that would show"
    " it (a ticket or a change of its own); a push or a re-run whose only purpose"
    " is a new run is refused"
)
LOG = "Failed check log: test: https://github.com/owner/project/runs/8"
LINE = (
    "RED CAUSE owner/project#1: test: log https://github.com/owner/project/runs/8; "
    + SENTENCE
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
    """The sweep's RED CAUSE line."""

    def test_the_rule_is_pinned(self) -> None:
        """The rule's words are the ones the ticket asks for."""
        assert_that(causetext.RULE, equal_to(SENTENCE))

    def test_a_red_check_prints_its_log_and_the_rule(self) -> None:
        """A failed check gets a RED CAUSE line naming its log."""
        lines = sweep(world.make_world()).out.splitlines()
        assert_that(LINE in lines, equal_to(True))

    def test_an_actions_check_names_its_job(self) -> None:
        """A check of a workflow run is located by the run and the job."""
        check = shapes.CheckRun(id=8, name="test", finished=True, failed=True, run=5)
        assert_that(
            causeline.log_location("o/r", check),
            equal_to("https://github.com/o/r/actions/runs/5/job/8"),
        )

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

    def test_the_fix_ci_suggestion_prints_each_failed_checks_log(self) -> None:
        """A red PR's FIX_CI brief has the log line right after its Task."""
        header, lines = suggestions.third(pr_three(world.RED))
        assert_that(header, contains_string("fix the CI"))
        assert_that(lines[1].startswith("Task: "), equal_to(True))
        assert_that(lines[2], equal_to(LOG))
        assert_that(matching(lines, "Failed check"), equal_to([LOG]))

    def test_a_brief_with_no_failed_check_has_no_log_line(self) -> None:
        """A PR whose check passed gets a brief with no log line."""
        lines = suggestions.third(pr_three(world.GREEN))[1]
        assert_that(matching(lines, "Failed check"), equal_to([]))

    def test_the_log_is_printed_without_formatting(self) -> None:
        """A name with braces is printed as it is."""
        spec = dataclasses.replace(make(brief.Kind.FIX_CI), logs=["a{b}: x/{y}"])
        assert_that(brief.build(spec), contains_string("Failed check log: a{b}: x/{y}"))
