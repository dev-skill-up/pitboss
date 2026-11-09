"""Tests for the rows a ticket promises to pass that the table marks otherwise (pitboss#279)."""

import unittest

from hamcrest import assert_that, contains_string, empty, equal_to, has_length

from .. import ticketrows
from . import linting

TABLE = (
    "## Rows\n\n"
    "| row | kind |\n"
    "|---|---|\n"
    "| the build is reproducible | must |\n"
    "| the release is signed | {tag} |\n"
)
PROMISE = "Done-when: every `must` test passes.\n"
ESCAPE = "Done-when: every row passes or is n/a with the reason written here.\n"
HONEST = "Done-when: the `must` rows pass.\n"


def ticket(done: str, tag: str = "policy") -> str:
    """A ticket body.

    Args:
        done: its Done-when paragraph.
        tag: the tag of the table's second row.

    Returns:
        The text.
    """
    return f"{TABLE.format(tag=tag)}\n{done}"


class TestRowsPass(unittest.TestCase):
    """What the finding refuses and what it lets through."""

    def test_a_policy_platform_or_decision_row_under_every_row_passes(self) -> None:
        """The quire#828 shape: a finding for each tag."""
        for tag in ticketrows.TAGS:
            found = ticketrows.findings("t", ticket(PROMISE, tag))
            assert_that(found, has_length(1))
            assert_that(found[0], contains_string(f"| the release is signed | {tag}"))

    def test_the_finding_states_both_rules(self) -> None:
        """The two rules are in the output, not in a doc."""
        found = ticketrows.findings("t", ticket(PROMISE))[0]
        assert_that(found, contains_string("never stricter than its parent's"))
        assert_that(found, contains_string("never listed as a row the ticket makes"))

    def test_a_done_when_that_does_not_promise_every_row_is_let_through(self) -> None:
        """Only an all-rows promise is refused."""
        assert_that(ticketrows.findings("t", ticket(HONEST)), empty())

    def test_a_table_with_no_tagged_row_is_let_through(self) -> None:
        """Every row passes, and none is policy."""
        assert_that(ticketrows.findings("t", ticket(PROMISE, "must")), empty())

    def test_the_heading_form_of_the_done_when_is_read(self) -> None:
        """``## Done-when`` then the paragraph."""
        body = ticket("## Done-when\n\nAll rows pass.\n")
        assert_that(ticketrows.findings("t", body), has_length(1))

    def test_a_tag_in_backticks_in_a_list_item_is_a_tagged_row(self) -> None:
        """The nearest spelling of a tag: a list item, not a table."""
        body = "- the release is signed (`platform`)\n\n" + PROMISE
        assert_that(ticketrows.findings("t", body), has_length(1))

    def test_the_word_in_prose_is_not_a_tag(self) -> None:
        """A list item that only says platform is no tagged row."""
        body = "- the platform builds\n\n" + PROMISE
        assert_that(ticketrows.findings("t", body), empty())

    def test_a_tag_in_a_cell_with_other_words_is_not_a_tag(self) -> None:
        """A table cell is a tag only when it is the tag alone."""
        body = TABLE.format(tag="the policy file") + "\n" + PROMISE
        assert_that(ticketrows.findings("t", body), empty())

    def test_a_promise_with_an_escape_still_refuses_a_tagged_row(self) -> None:
        """The escape is the parent's wording; the row is still listed."""
        assert_that(ticketrows.findings("t", ticket(ESCAPE)), has_length(1))


class TestLintTicket(unittest.TestCase):
    """``pitboss lint ticket``."""

    def test_it_prints_the_finding_and_exits_1(self) -> None:
        """A refused ticket."""
        done = linting.lint("ticket", linting.write_text("t.md", ticket(PROMISE)))
        assert_that(done.code, equal_to(1))
        assert_that(done.out, contains_string("(rows-pass)"))

    def test_it_prints_ok_for_a_ticket_in_form(self) -> None:
        """An accepted ticket."""
        done = linting.lint("ticket", linting.write_text("t.md", ticket(HONEST)))
        assert_that(done.code, equal_to(0))
        assert_that(done.out, equal_to("ok\n"))
