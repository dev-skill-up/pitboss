"""The lints the folded tickets asked of a PR body (pitboss#444, item 6)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, empty, equal_to, has_length

from .. import adoptline, evidence, expansion, forms, phrases, quotedplan, reviews
from .test_report import facts

HEAD = "a" * 40
OTHER = "b" * 40
PHRASES = phrases.parse(
    "half-done\t\\bthe part that\\b\tthe part that is left\tUse the Done-when as"
    " written.\n",
    "test",
)
ADOPT = "`adopt` (tools/adopt of repository-prototype) made this pull request"


def block(command: str, output: str) -> str:
    """A block that ``pitboss expand`` made.

    Args:
        command: the command row.
        output: its output.

    Returns:
        The fenced text.
    """
    return expansion.block(command, expansion.Outcome(status=0, output=output))


def body(*parts: str) -> str:
    """A body with a Head line, an Evidence heading and the parts.

    Args:
        parts: the lines after the heading.

    Returns:
        The text.
    """
    return "\n".join(
        ["Fixes o/r#1", "", f"Head: {HEAD}", "", "## Evidence", "", *parts]
    )


def named(text: str, check: str) -> Sequence[str]:
    """The findings of a body that end in a check's name.

    Args:
        text: the body.
        check: the check.

    Returns:
        The findings.
    """
    subject = forms.Subject(name="b", body=text, head=HEAD)
    return [each for each in forms.pr_body(subject) if each.endswith(f"({check})")]


class TestRevParseBlock(unittest.TestCase):
    """The block of ``git rev-parse HEAD`` prints the body's head."""

    def test_t329_a_block_that_prints_another_sha_is_refused(self) -> None:
        """The Head line moved and the block did not: both SHAs are named."""
        found = named(body(block("git rev-parse HEAD", OTHER + "\n")), "rev-parse-head")
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string(OTHER))
        assert_that(found[0], contains_string(HEAD))

    def test_t329_a_block_that_prints_the_head_passes(self) -> None:
        """The same body with the output of the head."""
        found = named(body(block("git rev-parse HEAD", HEAD + "\n")), "rev-parse-head")
        assert_that(found, empty())

    def test_t329_another_command_is_not_read(self) -> None:
        """A block of any other command prints what it prints."""
        found = named(body(block("git log -1", OTHER + "\n")), "rev-parse-head")
        assert_that(found, empty())


class TestExpandOutput(unittest.TestCase):
    """A words check reads the prose of a body, not the output of a command."""

    def test_t223_a_refused_word_in_an_expand_block_passes(self) -> None:
        """A Plan-mandated `git diff` row prints the word in its output."""
        text = body(block("git diff main", "the part that changed\n"))
        assert_that(phrases.findings(quotedplan.mask(text), "b", PHRASES), empty())

    def test_t223_the_same_word_in_the_prose_is_refused(self) -> None:
        """The control: outside a block the word is found, on its line."""
        text = body("It is the part that is left.")
        found = phrases.findings(quotedplan.mask(text), "b", PHRASES)
        assert_that(found, has_length(1))

    def test_t223_the_expand_block_checks_stay(self) -> None:
        """A block typed by hand is still a hand-typed row."""
        text = body("```\n$ git diff main\nthe part that changed\n```")
        assert_that(named(text, "hand-typed"), has_length(1))


class TestQuotedDoneWhen(unittest.TestCase):
    """The phrase lint passes the Plan's copy of a Done-when item."""

    def test_t413_a_copied_done_when_row_passes_and_the_prose_is_refused(self) -> None:
        """ "names the part that dominates" in a numbered Plan row, then in prose."""
        words = "names the part that dominates"
        plan = f"## Plan\n\n1. {words}\n"
        assert_that(phrases.findings(quotedplan.mask(plan), "b", PHRASES), empty())
        prose = f"## Notes\n\nThe change {words}.\n"
        found = phrases.findings(quotedplan.mask(prose), "b", PHRASES)
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("half-done"))


class TestAdoptBody(unittest.TestCase):
    """A body that ``adopt`` made is reviewed as the script."""

    def test_t423_the_two_rows_of_the_script_are_not_hand_typed(self) -> None:
        """`git rev-parse HEAD` and `git show --stat` in a body adopt made."""
        text = (
            f"{ADOPT}\n\n## Evidence\n\n$ git rev-parse HEAD\n{HEAD}\n$ git show"
            " --stat\n"
        )
        assert_that(evidence.hand_typed(text), empty())

    def test_t423_the_same_rows_in_any_other_body_are_hand_typed(self) -> None:
        """No adopt line: both rows are refused."""
        text = "## Evidence\n\n$ git rev-parse HEAD\n$ git show --stat\n"
        assert_that(evidence.hand_typed(text), equal_to([3, 4]))

    def test_t423_a_row_of_another_command_is_still_hand_typed(self) -> None:
        """One hand-typed row after a command that is not in the script's two."""
        text = f"{ADOPT}\n\n## Evidence\n\n$ git rev-parse HEAD\n$ nox -s tests\nOK\n"
        assert_that(evidence.hand_typed(text), equal_to([6]))

    def test_t423_the_sweep_says_the_review_is_of_the_script(self) -> None:
        """The reviewer line names tools/adopt, and only for such a PR."""
        pull = facts(reviews.Standing.NONE, body=f"{ADOPT}\n\nmore\n")
        said = adoptline.lines(pull)
        assert_that(said[0], contains_string("ADOPT-REVIEW o/r#7"))
        assert_that(said[0], contains_string("the review is of the script"))
        assert_that(adoptline.lines(facts(reviews.Standing.NONE)), empty())
