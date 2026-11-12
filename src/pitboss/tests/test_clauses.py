"""C27: every rule line of the owner's memory is mapped to a rule (keyword: clauses)."""

import json
import pathlib
import tempfile
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import clauses, phrases, rules
from . import world

REGISTER = (
    "A1\t2026-11-04\tenforced\tAn approved Plan is never"
    " edited\tflowstate.plan_edited_without_ruling\ttest_x.test_a1_a\nZ9\t2026-11-04\topen\tNot"
    " yet\t-\t-\nY8\t2026-11-04\tenforced\tNo tests\t-\t\n"
)
ROWS, _ = rules.parse(REGISTER)
TABLE = (
    "memory:MEMORY.md\t- APPROVED PLAN\tA1\tplan\n"
    "memory:a.md\tdescription\toutside: a fact\t-\n"
)
LINES = [("memory:MEMORY.md", "- APPROVED PLAN"), ("memory:a.md", "description")]


def found(table: str, corpus: Sequence[tuple[str, str]] = LINES) -> Sequence[str]:
    """The findings of a table against the fixture register.

    Args:
        table: the table.
        corpus: the clauses read.

    Returns:
        The findings.
    """
    return list(clauses.findings(table, ROWS, corpus))


class TestFindings(unittest.TestCase):
    """What the check refuses."""

    def test_c27_a_mapped_corpus_has_no_finding(self) -> None:
        """Every clause has its row, the rule is enforced and holds the needle."""
        assert_that(found(TABLE), equal_to([]))

    def test_c27_an_unmapped_clause_is_listed(self) -> None:
        """A clause with no row is named."""
        extra = [*LINES, ("memory:MEMORY.md", "- NEW RULE")]
        assert_that(
            found(TABLE, extra),
            equal_to(["memory:MEMORY.md '- NEW RULE': no row in clauses.tsv"]),
        )

    def test_c27_a_row_of_a_clause_that_is_gone_is_listed(self) -> None:
        """A row whose clause the source no longer has is stale."""
        said = found(TABLE, LINES[:1] + [("memory:a.md", "how-to-apply")])
        assert_that("\n".join(said), contains_string("not in the corpus"))

    def test_c27_a_missing_open_or_testless_rule_is_refused(self) -> None:
        """An id the register lacks, an open rule and a rule with no tests."""
        for rule, word in (("Q1", "no rule"), ("Z9", "open"), ("Y8", "no tests")):
            table = f"memory:a.md\tdescription\t{rule}\tplan\n"
            said = found(table, [("memory:a.md", "description")])
            assert_that(said[0], contains_string(word))

    def test_c27_a_needle_no_rule_holds_is_refused(self) -> None:
        """The tests cover the clause only when a mapped rule holds its word."""
        table = "memory:a.md\tdescription\tA1\tmerge\n"
        said = found(table, [("memory:a.md", "description")])
        assert_that(said[0], contains_string("no mapped rule holds 'merge'"))

    def test_c27_an_outside_with_no_reason_is_refused(self) -> None:
        """Outside says why."""
        table = "memory:a.md\tdescription\toutside: \t-\n"
        said = found(table, [("memory:a.md", "description")])
        assert_that(said[0], contains_string("no reason"))

    def test_c27_a_row_with_a_missing_field_is_refused(self) -> None:
        """A short row is an error."""
        with self.assertRaises(ValueError):
            clauses.parse("a\tb\n")


class TestCorpus(unittest.TestCase):
    """The sources are read."""

    def test_c27_memory_and_ticket_clauses_are_read(self) -> None:
        """Bullets, description and How to apply lines, numbered cases and comments."""
        folder = pathlib.Path(tempfile.mkdtemp())
        (folder / "MEMORY.md").write_text("# t\n- ONE rule\n- TWO\n")
        (folder / "t.md").write_text("description: d\n**How to apply:** x\n")
        said = clauses.memory(folder)
        assert_that(
            said,
            equal_to(
                [
                    ("memory:MEMORY.md", "- ONE rule"),
                    ("memory:MEMORY.md", "- TWO"),
                    ("memory:t.md", "description"),
                    ("memory:t.md", "how-to-apply"),
                ]
            ),
        )
        body = "1. before\n### Cases\n1. a\n2. b\n"
        got = clauses.ticket(body, json.dumps([{"id": 7}]))
        assert_that(
            got,
            equal_to(
                [
                    ("ticket:444", "case 1"),
                    ("ticket:444", "case 2"),
                    ("ticket:444", "comment 7"),
                ]
            ),
        )


class TestShipped(unittest.TestCase):
    """The shipped table against the shipped register, and the command."""

    def test_c27_the_shipped_table_has_no_finding(self) -> None:
        """Every row names enforced rules that hold its needle."""
        register, _ = rules.parse(phrases.shipped_text("rules.tsv"))
        text = phrases.shipped_text("clauses.tsv")
        assert_that(list(clauses.findings(text, register, [])), equal_to([]))

    def test_c27_the_command_lists_an_unmapped_line_and_exits_1(self) -> None:
        """A memory folder with a rule line no row names fails the command."""
        folder = pathlib.Path(tempfile.mkdtemp())
        (folder / "MEMORY.md").write_text("- A BRAND NEW RULE nobody mapped\n")
        done = world.invoke(
            world.make_world(), "clauses", "check", "--memory", str(folder)
        )
        assert_that(done.code, equal_to(1))
        assert_that(done.out, contains_string("A BRAND NEW RULE"))

    def test_c27_the_command_without_a_corpus_checks_the_table(self) -> None:
        """No option: the table alone, and it passes."""
        done = world.invoke(world.make_world(), "clauses", "check")
        assert_that((done.code, "clauses check: ok" in done.out), equal_to((0, True)))

    def test_c27_the_command_reads_the_ticket(self) -> None:
        """A ticket with an unmapped case fails; a mapped one passes."""
        folder = pathlib.Path(tempfile.mkdtemp())
        (folder / "b.txt").write_text("### Cases\n1. a\n99. unmapped\n")
        (folder / "c.json").write_text("[]")
        done = world.invoke(
            world.make_world(),
            "clauses",
            "check",
            "--ticket-body",
            str(folder / "b.txt"),
            "--ticket-comments",
            str(folder / "c.json"),
        )
        assert_that(done.code, equal_to(1))
        assert_that(done.out, contains_string("case 99"))
