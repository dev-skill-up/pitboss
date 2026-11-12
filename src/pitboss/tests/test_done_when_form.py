"""A20: plan-check refuses a Done-when item not stated as "X demonstrated by Y".

Owner, 2026-11-11 02:45Z (pitboss#444, keyword: done-when-form).
"""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, empty, equal_to, has_length

from .. import plandonewhen, plantickets
from . import fakes

LEAD = "Each item is demonstrated by the named test failing on main."
ITEMS = "1. A rule, demonstrated by a test.\n2. Another rule.\n"
SLUG = "owner/project#9"


def asked(ticket: str) -> Sequence[str]:
    """The findings ``plan-check`` makes of a ticket's form.

    Args:
        ticket: the ticket's text.

    Returns:
        The findings that start with ``done-when-form``.
    """
    github = fakes.github({"repos/owner/project/issues/9": {"body": ticket}})
    found = plantickets.done_when(github, SLUG, "owner/project", "Fixes #9\n")
    return [each for each in found if each.startswith(plandonewhen.FORM)]


class TestForm(unittest.TestCase):
    """An item says what demonstrates it, or a lead line says it for all."""

    def test_a20_an_item_with_no_demonstration_is_refused(self) -> None:
        """The first one is named."""
        found = asked(f"## Done when\n\n{ITEMS}")
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("the first one is: Another rule."))

    def test_a20_a_lead_line_states_it_for_every_item(self) -> None:
        """The nearest input it must still accept: the form of pitboss#444."""
        assert_that(asked(f"## Done when\n\n{LEAD}\n\n{ITEMS}"), empty())

    def test_a20_every_item_demonstrated_passes(self) -> None:
        """Each says it itself."""
        both = ITEMS.replace("Another rule.", "Another rule, demonstrated by a test.")
        assert_that(asked(f"## Done when\n\n{both}"), empty())

    def test_a20_a_ticket_with_no_done_when_has_no_item(self) -> None:
        """The missing section is another check's."""
        assert_that(plandonewhen.form("Just text."), equal_to([]))

    def test_a20_a_lead_line_that_names_no_demonstration_does_not_count(self) -> None:
        """ "Each item is a rule" says nothing of what shows it."""
        found = asked("## Done when\n\nEach item is a rule.\n\n1. A rule.\n")
        assert_that(found, has_length(1))
