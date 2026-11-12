"""The Done-when's comparison is a test: it fails when the pairing is false (#444).

``donewhen.tsv`` pairs each item of the ticket's Done-when with its tests; the
tests here fail when an item is missing, names a test or a rule id that is not
there, or a timeline is not in the scenario directory, and ``rules done-when`` is
the one command that also runs them on a base (keyword: done-when-check).
"""

import argparse
import pathlib
import tempfile
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, empty, equal_to

from .. import donewhencheck, donewhenrun, phrases
from .test_rules import ran, shipped_rows

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


def refused(head: bool, base: bool) -> Sequence[str]:
    """The refusals when every test is there and passes (or not) on each side.

    Args:
        head: whether every test passes on the head.
        base: whether every test passes on the base.

    Returns:
        The findings.
    """
    tests = {
        t for each in items() for t in donewhencheck.tests_of(each, shipped_rows())
    }
    everywhere = donewhencheck.Checks(
        exists=lambda _: True,
        head={t: head for t in tests},
        base={t: base for t in tests},
    )
    return donewhencheck.refusals(items(), shipped_rows(), everywhere)


def command(pairing: str, ref: str) -> tuple[int, str]:
    """Run ``rules done-when`` on a pairing against a base.

    Args:
        pairing: the text of a pairing.
        ref: the base.

    Returns:
        The exit status and the standard output.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".tsv") as file:
        file.write(pairing)
        file.flush()
        return ran(
            argparse.Namespace(
                action="done-when",
                pairing=file.name,
                ref=ref,
                repo=str(HERE.parents[3]),
            )
        )


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

    def test_the_comparison_is_ok_when_the_head_passes_and_the_base_fails(self) -> None:
        """No finding."""
        assert_that(refused(True, False), empty())
        assert_that(donewhencheck.verdict([]), equal_to("done-when check: ok"))


class TestThePairingIsFalse(unittest.TestCase):
    """The comparison names each fault."""

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

    def test_a_test_that_fails_on_the_head_or_passes_on_the_base_is_found(self) -> None:
        """Every test fails on the head; nothing fails on the base."""
        assert_that(refused(False, False)[0], contains_string("fails on the head"))
        assert_that(
            refused(True, True)[0], equal_to("item 1: no named test fails on the base")
        )


class TestTheCommand(unittest.TestCase):
    """``rules done-when`` runs the tests on the head and on the base."""

    def test_a_base_the_head_equals_refuses_naming_the_item(self) -> None:
        """HEAD as the base: the test passes on both, so nothing fails on the base."""
        pairing = "7\ttest_brief.test_each_brief_starts_with_the_original_goal\n"
        status, said = command(pairing, "HEAD")
        assert_that(status, equal_to(1))
        assert_that(said, contains_string("item 7: no named test fails on the base"))

    def test_a_test_that_is_not_there_refuses(self) -> None:
        """The verdict is one line."""
        status, said = command("7\ttest_rules.test_nothing\n", "HEAD")
        assert_that([status, said.count("\n")], equal_to([1, 1]))
        assert_that(said, contains_string("refused, 1 findings"))
