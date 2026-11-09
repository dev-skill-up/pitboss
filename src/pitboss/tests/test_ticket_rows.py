"""Tests for the rows a ticket promises to pass that the table marks (pitboss#279)."""

import unittest
from typing import Mapping

from hamcrest import assert_that, contains_string, equal_to

from .. import ticketrows
from . import linting, world

TABLE = "| the build is reproducible | must |\n| the release is signed | {tag} |\n"
PROMISE = "Done-when: every `must` test passes.\n"
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


def lint_ticket(done: str) -> world.Result:
    """Run ``pitboss lint ticket`` on a ticket.

    Args:
        done: its Done-when paragraph.

    Returns:
        What the command did.
    """
    return linting.lint("ticket", linting.write_text("t.md", ticket(done)))


def counts(bodies: Mapping[str, str]) -> Mapping[str, int]:
    """How many findings each body gets.

    Args:
        bodies: a label and a ticket body.

    Returns:
        The label and the number of findings.
    """
    found = {label: ticketrows.findings("t", each) for label, each in bodies.items()}
    return {label: len(each) for label, each in found.items()}


class TestRowsPass(unittest.TestCase):
    """What the finding refuses and what it lets through."""

    def test_every_tag_under_a_promise_of_every_row_is_refused(self) -> None:
        """The quire#828 shape: a finding for each tag."""
        found = {tag: ticket(PROMISE, tag) for tag in ticketrows.TAGS}
        assert_that(counts(found), equal_to({tag: 1 for tag in ticketrows.TAGS}))

    def test_the_finding_states_both_rules(self) -> None:
        """The two rules are in the output, not in a doc."""
        found = ticketrows.findings("t", ticket(PROMISE))[0]
        assert_that(found, contains_string("never stricter than its parent's"))
        assert_that(found, contains_string("is never listed as a row the ticket"))
        assert_that(found, contains_string("| the release is signed | policy"))

    def test_what_is_let_through(self) -> None:
        """No promise of every row, no tagged row, a tag among other words."""
        let = {
            "promise of some rows": ticket(HONEST),
            "no tagged row": ticket(PROMISE, "must"),
            "tag among words": ticket(PROMISE, "the policy file"),
            "word in prose": f"- the platform builds\n\n{PROMISE}",
        }
        assert_that(counts(let), equal_to({label: 0 for label in let}))

    def test_what_is_refused_beside_the_table_form(self) -> None:
        """The heading form, a list item with a tag, an escape that is kept."""
        item = "- the release is signed (`platform`)\n\n"
        refused = {
            "heading form": ticket("## Done-when\n\nAll rows pass.\n"),
            "list item": item + PROMISE,
            "escape kept": ticket("Done-when: every row passes or is n/a.\n"),
        }
        assert_that(counts(refused), equal_to({label: 1 for label in refused}))


class TestLintTicket(unittest.TestCase):
    """``pitboss lint ticket``."""

    def test_a_refused_ticket_exits_1_and_one_in_form_prints_ok(self) -> None:
        """The command's two outcomes."""
        refused = lint_ticket(PROMISE)
        passed = lint_ticket(HONEST)
        assert_that(refused.out, contains_string("(rows-pass)"))
        assert_that((refused.code, passed.code, passed.out), equal_to((1, 0, "ok\n")))
