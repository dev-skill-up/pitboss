"""An Evidence block records its head; another head is refused (pitboss#398)."""

import argparse
import pathlib
import subprocess
import unittest
from typing import NoReturn, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import evidence, expand_commands, expansion
from . import diffrepo
from .linting import HEAD, OK, lint, write_text
from .plancheckrun import body_of, passed, plan_check, refused_with
from .repositories import run_git
from .test_expand_commands import check, expanded

OTHER = "b" * 40
NEAR = HEAD[:-1] + "b"
COMMAND = "nox -s tests"
SECTION = "## Evidence\n\n"
ROWS = "1. `rg -n x src/`\n"


def block_of(head: str) -> str:
    """The Evidence block of a command, expanded at a head.

    Args:
        head: the head the block records; none when empty.

    Returns:
        The block.
    """
    return expansion.block(COMMAND, OK, head)


class TestRecord(unittest.TestCase):
    """``expand`` writes the head it ran at."""

    def test_the_opening_line_records_the_head(self) -> None:
        """Done-when: the head of the checkout is in each block's header."""
        repo = diffrepo.make_repository(self)
        done = expanded("$ echo a\n$ echo b\n", "--cwd", str(repo.root))
        headers = [each for each in done.out.splitlines() if expansion.MARK in each]
        recorded = [expansion.recorded_head(each) for each in headers]
        assert_that(recorded, equal_to([repo.first, repo.first]))

    def test_a_directory_git_cannot_read_records_none(self) -> None:
        """The record is a fact of git; with none the header has the digest only."""

        def failing(command: Sequence[str], **_: object) -> NoReturn:
            raise subprocess.CalledProcessError(128, command)

        args = argparse.Namespace(cwd=".", safe_run=failing)
        assert_that(expand_commands.head_of(args), equal_to(""))

    def test_a_block_with_a_head_is_still_produced_and_collapses(self) -> None:
        """The head is no part of the digest, and a re-expansion does not move it."""
        text = SECTION + block_of(HEAD)
        assert_that(evidence.has_produced(text), equal_to(True))
        again = expansion.collapsed(SECTION + block_of(OTHER))
        assert_that(expansion.collapsed(text), equal_to(again))


class TestLint(unittest.TestCase):
    """``lint pr-body --head`` refuses another head."""

    def test_only_the_heads_block_and_an_unrecorded_one_pass(self) -> None:
        """Done-when: the commit before, one digit off, the head, no record."""
        cases = {OTHER: True, NEAR: True, HEAD: False, "": False}
        for head, refused in cases.items():
            with self.subTest(head or "none"):
                checked = check(block_of(head))
                assert_that(checked.code == 1, equal_to(refused))
                if refused:
                    assert_that(checked.out, contains_string(f"`{COMMAND}`"))
                    assert_that(checked.out, contains_string(f"expanded at {head}"))

    def test_a_short_head_makes_the_block_a_typed_one(self) -> None:
        """The record is 40 digits; a short one is not a block expand produced."""
        header = f"pitboss-expand sha256={expansion.digest(f'$ {COMMAND}')} head=abc"
        body = write_text("body.md", f"```{header}\n$ {COMMAND}\n```\n")
        assert_that(lint("pr-body", body, "--head", HEAD).code, equal_to(1))


class TestFindings(unittest.TestCase):
    """The findings of the module."""

    def test_each_stale_block_is_named(self) -> None:
        """The command and the line of each block that is not the head's."""
        found = evidence.stale_heads(SECTION + block_of(OTHER), HEAD)
        assert_that([len(found), "(line 3)" in found[0]], equal_to([1, True]))

    def test_no_head_judges_nothing(self) -> None:
        """A head that is not known."""
        assert_that(evidence.stale_heads(SECTION + block_of(OTHER), ""), equal_to([]))


class TestPlanCheck(unittest.TestCase):
    """``plan-check`` refuses a block expanded at another commit."""

    def test_a_block_from_the_commit_before_the_head_is_refused(self) -> None:
        """Done-when: planted at the commit before the head; the head's is passed."""
        repo = diffrepo.make_repository(self)
        before = repo.first
        diffrepo.commit(repo, "doc/x.txt", "x\n")
        head = run_git(pathlib.Path(repo.root), "rev-parse", "HEAD").strip()
        old = plan_check(repo, body_of(ROWS, block_of(before)))
        new = plan_check(repo, body_of(ROWS, block_of(head)))
        said = [f"evidence-head: the Evidence block of `{COMMAND}`", "findings: 1"]
        assert_that(refused_with(old, *said), equal_to(True))
        assert_that(passed(new), equal_to(True))
