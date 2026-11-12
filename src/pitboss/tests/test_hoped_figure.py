"""T419: a key that is not a path, and a hoped-for figure (keyword: hoped-figure)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import donewhen, hopedfigure, plandonewhen
from . import fakes, test_done_when

KNOWN = donewhen.Known(kinds=frozenset(), commands=frozenset(), tree=fakes.directory())
KEY = (
    "Done-when: the allowlist line whose key is `bats/.github/workflows/check.yml`"
    " passes."
)
FILE = "Done-when: `bats/.github/workflows/check.yml` passes."
SPECIFIC = "Done-when:\n* The check catches the bare sleep in `a.js`.\n"
HOPED = (
    "Done-when:\n* At least 90% of the fixtures pass.\n* 12 of 15 specs are green.\n"
)


class TestHopedFigure(unittest.TestCase):
    """Both halves of the ticket."""

    def test_t419_a_key_is_not_a_missing_file(self) -> None:
        """A path the text calls a key is accepted."""
        assert_that(donewhen.missing_line("o/r#1", KEY, KNOWN), equal_to(""))

    def test_t419_a_file_that_does_not_exist_is_still_refused(self) -> None:
        """The same path with no key word."""
        said = donewhen.missing_line("o/r#1", FILE, KNOWN)
        assert_that(said, contains_string("file bats/.github/workflows/check.yml"))

    def test_t419_a_hoped_for_share_is_flagged(self) -> None:
        """Each item with a share or a count as the bar."""
        found = hopedfigure.findings(HOPED)
        assert_that(found, has_length(2))
        assert_that(found[0], contains_string("never part of the criteria"))

    def test_t419_a_specific_catch_is_not_flagged(self) -> None:
        """An item that names the catch."""
        assert_that(hopedfigure.findings(SPECIFIC), equal_to([]))

    def test_t419_plan_check_form_carries_it(self) -> None:
        """The form finding list holds it, with or without a lead line."""
        lead = (
            "Done-when:\nEach is demonstrated by `$ make test`.\n* At least 90% pass.\n"
        )
        assert_that(plandonewhen.form(lead), has_length(1))
        assert_that(plandonewhen.form(HOPED), has_length(3))

    def test_t419_next_prints_it(self) -> None:
        """``pitboss next TICKET`` prints the finding."""
        found = test_done_when.next_with_body(HOPED)
        assert_that(found.out, contains_string("hoped-figure"))
