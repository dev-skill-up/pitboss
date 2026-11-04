"""Tests for the ``How we got here`` section of an escalation (pitboss#168)."""

import re
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, has_item

from .. import analysis, brief, brieftext, shapes
from . import briefmake, linting, test_plan_revision

URL = "https://github.com/owner/project/pull/3#issuecomment-168"
MARK = "RULING NO ANALYSIS"
SECTION = (
    "## How we got here\n"
    "- round 1: the plan named no case; rule: Plan first; prevention: pitboss#12\n"
)
RULING = "Opus ruling\nRuling: do these steps\n"
CARD = "Escalate PR 3?\nHow we got here: two rejections, prevention pitboss#12\n"


def comment(body: str, author: str = "MEMBER", when: str = "1") -> shapes.Comment:
    """An issue comment.

    Args:
        body: its text.
        author: its author's association.
        when: its creation time.

    Returns:
        The comment.
    """
    return shapes.Comment(
        body=body, author_association=author, created_at=when, url=URL
    )


def marked(body: str) -> Sequence[str]:
    """The RULING NO ANALYSIS lines of a sweep of a world with one comment.

    Args:
        body: the text of PR 3's only comment.

    Returns:
        The lines.
    """
    sweep = test_plan_revision.outputs(comment(body))
    return re.findall(f"^{MARK} .*$", sweep[0], re.MULTILINE)


class TestSection(unittest.TestCase):
    """What counts as the section."""

    def test_the_words_as_a_heading_bold_or_a_label_count(self) -> None:
        """A heading, bold words, or a label with the analysis on the line."""
        found = {
            "## How we got here\nx\n": True,
            "# how we got here:\nx\n": True,
            "**How we got here**\nx\n": True,
            "How we got here: x\n": True,
            "Intro\n\nHow  we got here\nx": True,
            "": False,
            "Ruling: split\n": False,
            "## How we got here\n\n": False,
            "See how we got here below\nx\n": False,
            "How we got hereafter: x\n": False,
        }
        read = {each: analysis.has_section(each) for each in found}
        assert_that(read, equal_to(found))


class TestUnanalysed(unittest.TestCase):
    """Which ruling comment is named."""

    def test_the_newest_trusted_ruling_without_the_section(self) -> None:
        """A newer ruling with the section hides an older one without."""
        old = comment(RULING, when="1")
        new = comment(RULING + SECTION, when="2")
        trusted = {"MEMBER"}
        assert_that(analysis.unanalysed([old, new], trusted), equal_to([]))
        assert_that(
            analysis.unanalysed([new, comment(RULING, when="3")], trusted),
            equal_to([URL]),
        )

    def test_no_ruling_or_a_stranger_names_nothing(self) -> None:
        """Only a trusted author's ruling comment counts."""
        trusted = {"MEMBER"}
        assert_that(analysis.unanalysed([comment("LGTM")], trusted), equal_to([]))
        stranger = comment(RULING, author="NONE")
        assert_that(analysis.unanalysed([stranger], trusted), equal_to([]))


class TestSweepPrintsIt(unittest.TestCase):
    """The sweep line, end to end."""

    def test_a_ruling_without_the_section_is_named(self) -> None:
        """The line names the PR, the comment and the section."""
        lines = marked(RULING)
        assert_that(len(lines), equal_to(1))
        assert_that(lines[0], contains_string(f"{MARK} owner/project#3: {URL} has no"))
        assert_that(lines[0], contains_string("'How we got here' section"))

    def test_a_ruling_with_the_section_is_not(self) -> None:
        """A ruling in form prints no such line."""
        assert_that(marked(RULING + SECTION), equal_to([]))

    def test_a_comment_that_is_no_ruling_is_not(self) -> None:
        """Only a comment whose first line is `Opus ruling` is a ruling."""
        assert_that(marked("LGTM\n"), equal_to([]))


def lint_card(text: str) -> tuple[object, str]:
    """Lint a card's text.

    Args:
        text: the card's question and reason.

    Returns:
        The exit code and the output.
    """
    done = linting.lint("owner-card", linting.write_text("card.txt", text))
    return done.code, done.out


class TestOwnerCard(unittest.TestCase):
    """``pitboss lint owner-card``."""

    def test_a_card_with_the_section_is_ok(self) -> None:
        """The analysis is on the card."""
        assert_that(lint_card(CARD), equal_to((0, "ok\n")))

    def test_a_card_without_it_is_refused(self) -> None:
        """The finding names the check."""
        code, out = lint_card("Escalate PR 3?\nTwo rejections.\n")
        assert_that(code, equal_to(1))
        assert_that(out, contains_string("(how-we-got-here)"))

    def test_a_card_with_an_empty_section_is_refused(self) -> None:
        """The words alone are not an analysis."""
        assert_that(lint_card("Q?\nHow we got here:\n")[0], equal_to(1))


class TestRulingBrief(unittest.TestCase):
    """The Opus agent's brief."""

    def test_it_carries_the_section_and_refuses_without_it(self) -> None:
        """The brief has the line, the refusal, and the ruling carries it too."""
        found = briefmake.text(brief.Kind.RULING)
        assert_that(found, contains_string("\nHow we got here: "))
        assert_that(found, contains_string("Refuse to rule without it"))
        assert_that(found, contains_string("a section headed `How we got here`"))
        assert_that(found.splitlines(), has_item(brieftext.RULING_HOW))
        assert_that("{" in found, equal_to(False))
