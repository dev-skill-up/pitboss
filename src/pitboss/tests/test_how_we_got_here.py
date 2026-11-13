"""Tests for the ``How we got here`` section of an escalation (pitboss#168)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to, has_item

from .. import analysis, brief, brieftext
from . import briefmake, linting

CARD = "Escalate PR 3?\nHow we got here: two rejections, prevention pitboss#12\n"


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
