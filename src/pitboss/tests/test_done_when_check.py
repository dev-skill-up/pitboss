"""The Done-when's pairing is a test: it fails when the pairing is false (#444).

``donewhen.tsv`` pairs each item of the ticket's Done-when with its tests; the
tests here fail when an item is missing, names a test or a rule id that is not
there, or a timeline is not in the scenario directory (keyword: done-when-check).
That the tests fail on the base is ``pitboss base-check`` (test_base_check).
"""

import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, empty, equal_to

from .. import donewhencheck, donewhenrun, phrases
from .test_rules import shipped_rows

HERE = pathlib.Path(__file__)
NUMBERS = [str(each) for each in range(1, 15)]
PULLS = {
    "bats-lang-bats": (650,),
    "bats-lang-quire": (1083, 1104),
    "dev-skill-up-pitboss": (460, 463, 465, 468, 470),
}
TIMELINES = [f"{repo}-{number}" for repo, each in PULLS.items() for number in each]


def items(text: str = "") -> Sequence[donewhencheck.Item]:
    """The items of the shipped pairing, or of a text.

    Args:
        text: a pairing; the shipped one when empty.

    Returns:
        The items.
    """
    return donewhencheck.parse(text or phrases.shipped_text("donewhen.tsv"))


class TestThePairing(unittest.TestCase):
    """The shipped pairing is complete and true."""

    def test_every_item_of_the_done_when_is_paired(self) -> None:
        """Items 1 to 14, exactly."""
        assert_that([each.number for each in items()], equal_to(NUMBERS))

    def test_every_named_test_and_rule_is_there(self) -> None:
        """No test is missing, no id has no checked row, no item names nothing."""
        assert_that(
            donewhencheck.missing(items(), shipped_rows(), donewhenrun.exists), empty()
        )

    def test_the_eight_timelines_are_in_the_scenario_directory(self) -> None:
        """The captured PRs the ticket names, exactly."""
        found = sorted(each.stem for each in (HERE.parent / "scenarios").iterdir())
        assert_that(found, equal_to(TIMELINES))


class TestThePairingIsFalse(unittest.TestCase):
    """The pairing names each fault."""

    def test_a_test_that_is_not_there_an_id_with_no_row_and_an_empty_item(self) -> None:
        """A test of no module, A9999 and an item that names nothing."""
        pairing = "1\ttest_x.test_y\n2\tA9999\n3\t"
        found = donewhencheck.missing(
            items(pairing), shipped_rows(), donewhenrun.exists
        )
        assert_that(
            found,
            equal_to(
                [
                    "item 1: test_x.test_y is not there",
                    "item 2: A9999 is not there",
                    "item 3: names no test",
                ]
            ),
        )
