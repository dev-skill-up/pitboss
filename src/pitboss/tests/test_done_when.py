"""The Done-when's comparison is a test: it fails when the pairing is false (#444).

``donewhen.tsv`` pairs each item of the ticket's Done-when with its tests; the
tests here fail when an item is missing, names a test or a rule id that is not
there, or a timeline is not in the scenario directory, and ``rules done-when`` is
the one command that also runs them on a base (keyword: done-when-check).
"""

import argparse
import io
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout

from hamcrest import assert_that, contains_string, empty, equal_to

from .. import donewhen, donewhenrun, phrases, rules, rules_commands

HERE = pathlib.Path(__file__).parent
NUMBERS = [str(each) for each in range(1, 15)]
TIMELINES = [
    "bats-lang-bats-650",
    "bats-lang-quire-1083",
    "bats-lang-quire-1104",
    "dev-skill-up-pitboss-460",
    "dev-skill-up-pitboss-463",
    "dev-skill-up-pitboss-465",
    "dev-skill-up-pitboss-468",
    "dev-skill-up-pitboss-470",
]


def rows() -> list[rules.Row]:
    """The rows of the shipped register.

    Returns:
        The rows.
    """
    return list(rules.parse(phrases.shipped_text("rules.tsv"))[0])


def items(text: str = "") -> list[donewhen.Item]:
    """The items of the shipped pairing, or of a text.

    Args:
        text: a pairing; the shipped one when empty.

    Returns:
        The items.
    """
    return list(donewhen.parse(text or phrases.shipped_text("donewhen.tsv")))


def checks(head: bool, base: bool) -> donewhen.Checks:
    """The knowledge that every test is there and passes (or not) on each side.

    Args:
        head: whether every test passes on the head.
        base: whether every test passes on the base.

    Returns:
        The checks.
    """
    tests = {t for each in items() for t in donewhen.tests_of(each, rows())}
    return donewhen.Checks(
        exists=lambda _: True,
        head={t: head for t in tests},
        base={t: base for t in tests},
    )


def command(pairing: str, ref: str) -> tuple[int, str]:
    """Run ``rules done-when`` on a pairing against a base.

    Args:
        pairing: the text of a pairing.
        ref: the base.

    Returns:
        The exit status and the standard output.
    """
    out = io.StringIO()
    status = 0
    with tempfile.TemporaryDirectory() as scratch:
        file = pathlib.Path(scratch) / "pairing.tsv"
        file.write_text(pairing, encoding="utf-8")
        args = argparse.Namespace(
            action="done-when", pairing=str(file), ref=ref, repo=str(HERE.parents[2])
        )
        with redirect_stdout(out):
            try:
                rules_commands.rules_check(args)
            except SystemExit as stop:
                status = int(stop.code or 0)
    return status, out.getvalue()


class TestThePairing(unittest.TestCase):
    """The shipped pairing is complete and true."""

    def test_every_item_of_the_done_when_is_paired(self) -> None:
        """Items 1 to 14, exactly."""
        assert_that([each.number for each in items()], equal_to(NUMBERS))

    def test_every_named_test_and_rule_is_there(self) -> None:
        """No test is missing, no id has no checked row, no item names nothing."""
        assert_that(donewhen.missing(items(), rows(), donewhenrun.exists), empty())

    def test_the_eight_timelines_are_in_the_scenario_directory(self) -> None:
        """The captured PRs the ticket names, exactly."""
        found = sorted(each.stem for each in (HERE / "scenarios").iterdir())
        assert_that(found, equal_to(TIMELINES))

    def test_the_comparison_is_ok_when_the_head_passes_and_the_base_fails(self) -> None:
        """No finding."""
        assert_that(donewhen.refusals(items(), rows(), checks(True, False)), empty())


class TestThePairingIsFalse(unittest.TestCase):
    """The comparison names each fault."""

    def test_an_item_that_names_a_test_that_is_not_there_is_found(self) -> None:
        """A test of no module."""
        found = donewhen.missing(items("1\ttest_x.test_y"), rows(), donewhenrun.exists)
        assert_that(found, equal_to(["item 1: test_x.test_y is not there"]))

    def test_an_id_with_no_row_and_an_item_with_no_token_are_found(self) -> None:
        """A9999 is no rule; item 3 names nothing."""
        found = donewhen.missing(items("2\tA9999\n3\t"), rows(), donewhenrun.exists)
        assert_that(
            found, equal_to(["item 2: A9999 is not there", "item 3: names no test"])
        )

    def test_a_test_that_fails_on_the_head_is_found(self) -> None:
        """Every test fails on the head."""
        found = donewhen.refusals(items(), rows(), checks(False, False))
        assert_that(found[0], contains_string("fails on the head"))

    def test_an_item_whose_tests_all_pass_on_the_base_is_found(self) -> None:
        """Nothing fails on the base."""
        found = donewhen.refusals(items(), rows(), checks(True, True))
        assert_that(found[0], equal_to("item 1: no named test fails on the base"))


class TestTheCommand(unittest.TestCase):
    """``rules done-when`` runs the tests on the head and on the base."""

    def test_a_base_the_head_equals_refuses_naming_the_item(self) -> None:
        """HEAD as the base: the test passes on both, so nothing fails on the base."""
        pairing = "7\ttest_rules.test_r2_names_id_is_a_word_match\n"
        status, said = command(pairing, "HEAD")
        assert_that(status, equal_to(1))
        assert_that(said, contains_string("item 7: no named test fails on the base"))

    def test_a_test_that_is_not_there_refuses(self) -> None:
        """The verdict is one line."""
        status, said = command("7\ttest_rules.test_nothing\n", "HEAD")
        assert_that([status, said.count("\n")], equal_to([1, 1]))
        assert_that(said, contains_string("refused, 1 findings"))
