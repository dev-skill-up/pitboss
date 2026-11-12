"""Every output and outside rule says what a program could decide (keyword: decidable).

Rule ids of ``decidable.tsv`` are the register's; the planted tests change one row
of the register or of the file and the check finds it.
"""

import dataclasses
import unittest

from hamcrest import assert_that, contains_string, empty, equal_to, has_length

from .. import decidable, phrases, rules

REGISTER, _BAD = rules.parse(phrases.shipped_text("rules.tsv"))
HELD = decidable.parse(phrases.shipped_text("decidable.tsv"))


class TestDecidable(unittest.TestCase):
    """The file against the register."""

    def test_the_shipped_file_matches_the_register(self) -> None:
        """Thirty rows of kind output or outside, each with a valid row."""
        assert_that(decidable.findings(REGISTER, HELD), empty())
        assert_that(HELD, has_length(30))

    def test_a_new_output_rule_without_a_row_is_found(self) -> None:
        """Planted: a rule of kind output that the file does not know."""
        extra = dataclasses.replace(REGISTER[0], id="Z9", kind="output")
        found = decidable.findings([*REGISTER, extra], HELD)
        assert_that(
            found, equal_to(["decidable: Z9 (output) has no row in decidable.tsv"])
        )

    def test_a_row_of_a_gone_rule_is_found(self) -> None:
        """Planted: a row for a rule that is enforced, or not there."""
        found = decidable.findings(REGISTER, {**HELD, "A1": ("outside", "x" * 40)})
        assert_that(found[0], contains_string("A1 is no output or outside rule"))

    def test_a_row_that_is_not_valid_is_found(self) -> None:
        """Planted: B13 checked by another function, a reason of a word, a verdict."""
        for row, held, said in (
            ("B13", ("checked", "x.y"), "B13 is checked by x.y"),
            ("B3", ("outside", "no"), "B3 is outside with no reason"),
            ("B3", ("maybe", ""), "the verdict 'maybe'"),
        ):
            with self.subTest(said):
                found = decidable.findings(REGISTER, {**HELD, row: held})
                assert_that(found[0], contains_string(said))
