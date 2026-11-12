"""R1 the register is checked, R2 it holds every rule of the coverage table.

Rule ids R1 and R2 are the Done-when items 1 and 2 of pitboss#444.
"""

import argparse
import dataclasses
import io
import pathlib
import unittest
from contextlib import redirect_stdout

from hamcrest import assert_that, contains_string, empty, equal_to, has_item, has_length

from .. import phrases, rules, rules_commands

HERE = pathlib.Path(__file__).parent
GOOD = "A1\t2026-01-01\tenforced\twords\trules.names_id\ttest_rules.test_r1_planted\n"


def _findings(text: str) -> list[str]:
    rows, bad = rules.parse(text)
    return [
        *bad,
        *rules.findings(
            rows, rules_commands.function_known, rules_commands.module_text
        ),
    ]


def _ran(register: str | None) -> tuple[int, str]:
    out = io.StringIO()
    status = 0
    with redirect_stdout(out):
        try:
            rules_commands.rules_check(
                argparse.Namespace(action="check", register=register)
            )
        except SystemExit as stop:
            status = int(stop.code or 0)
    return status, out.getvalue()


class TestCheck(unittest.TestCase):
    """The check passes the shipped register and fails each planted row."""

    def test_r1_the_shipped_register_passes(self) -> None:
        """No finding on the register pitboss ships."""
        assert_that(_findings(phrases.shipped_text("rules.tsv")), empty())

    def test_r1_planted(self) -> None:
        """The test the control row names."""
        assert_that(rules.KINDS, has_item("open"))

    def test_r1_a_row_without_tests_and_unknown_modules_are_found(self) -> None:
        """No test listed, no such function module, no such test module."""
        none = _findings(GOOD.replace("test_rules.test_r1_planted", ""))
        assert_that(none[0], contains_string("unknown-test: A1"))
        assert_that(rules_commands.function_known("nosuch.x"), equal_to(False))
        assert_that(rules_commands.module_text("nosuch"), equal_to(None))

    def test_r1_a_good_row_passes(self) -> None:
        """The control of the planted rows."""
        assert_that(_findings(GOOD.replace("A1", "R1")), empty())

    def test_r1_unknown_function_and_test_are_found(self) -> None:
        """A row naming a function or a test that is not there."""
        for old, new, word in (
            ("rules.names_id", "rules.no_such", "unknown-function"),
            ("test_r1_planted", "test_r1_missing", "unknown-test"),
        ):
            with self.subTest(word):
                found = _findings(GOOD.replace(old, new))
                assert_that(found[0], contains_string(f"{word}: A1"))

    def test_r1_test_without_the_id_is_found(self) -> None:
        """A test that exists but does not name its rule."""
        found = _findings(
            GOOD.replace(
                "test_r1_planted", "test_r1_the_shipped_register_passes"
            ).replace("A1", "Z9")
        )
        assert_that(found[-1], contains_string("test-without-id"))

    def test_r1_bad_row_unknown_kind_and_repeat_are_found(self) -> None:
        """A row with too few fields, a kind that is none, a repeated id."""
        found = _findings("A1\tx\n" + GOOD + GOOD.replace("enforced", "odd"))
        words = [each.split(":")[0] for each in found]
        assert_that(
            sorted(set(words)),
            equal_to(["bad-row", "duplicate-id", "test-without-id", "unknown-kind"]),
        )

    def test_r1_the_command_prints_ok_on_the_shipped_register(self) -> None:
        """``rules check`` exits 0 on the register pitboss ships."""
        status, printed = _ran(None)
        assert_that(status, equal_to(0))
        assert_that(printed, contains_string("rules check: ok"))

    def test_r1_the_command_refuses_a_bad_register(self) -> None:
        """``rules check`` exits 1 and names the unknown function."""
        status, printed = _ran(str(HERE / "bad_register.tsv"))
        assert_that(status, equal_to(1))
        assert_that(printed, contains_string("unknown-function"))


def table() -> list[str]:
    """The ids of the coverage table the package ships.

    Returns:
        The ids.
    """
    return phrases.shipped_text("coverage_ids.txt").split()


def shipped_rows() -> list[rules.Row]:
    """The rows of the register the package ships.

    Returns:
        The rows.
    """
    return list(rules.parse(phrases.shipped_text("rules.tsv"))[0])


class TestIds(unittest.TestCase):
    """The register holds the ids of the coverage table."""

    def test_r2_the_register_has_every_id_of_the_table(self) -> None:
        """Compare the table's 87 ids with the register's."""
        assert_that(table(), has_length(87))
        assert_that(rules.coverage_findings(shipped_rows(), table()), empty())

    def test_r2_outside_and_output_kinds_are_the_tables(self) -> None:
        """Exactly D4, D12, D13 and D14 are outside: a fifth, or one fewer, is found."""
        rows = shipped_rows()
        fifth = [
            dataclasses.replace(r, kind="outside") if r.id == "C8" else r for r in rows
        ]
        fewer = [
            dataclasses.replace(r, kind="output") if r.id == "D4" else r for r in rows
        ]
        assert_that(
            rules.coverage_findings(fifth, table()),
            has_item(contains_string("outside-set")),
        )
        assert_that(
            rules.coverage_findings(fewer, table()),
            has_item(contains_string("outside-set")),
        )

    def test_r2_an_extra_outside_row_is_found(self) -> None:
        """A table id with no row, and one that is open, are found."""
        rows = shipped_rows()
        gone = [r for r in rows if r.id != "A7"]
        opened = [
            dataclasses.replace(r, kind="open") if r.id == "B3" else r for r in rows
        ]
        assert_that(
            rules.coverage_findings(gone, table()),
            equal_to(["table-id: A7 has no row"]),
        )
        assert_that(
            rules.coverage_findings(opened, table()),
            equal_to(["table-kind: B3 is open"]),
        )

    def test_r2_the_shipped_check_has_the_table(self) -> None:
        """``rules check`` on the shipped register runs the table check and passes."""
        status, printed = _ran(None)
        assert_that([status, "outside-set" in printed], equal_to([0, False]))

    def test_r2_names_id_is_a_word_match(self) -> None:
        """``a7`` does not match ``a70``."""
        assert_that(rules.names_id("m.test_a7_x", "A7"), equal_to(True))
        assert_that(rules.names_id("m.test_a70_x", "A7"), equal_to(False))
