"""What the worktrees recorded of the hand-backs (keyword: standing, pitboss#507)."""

import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import handbackrecord, handbacks, handedread, running
from . import fakes, handbackworld, repositories

HEAD = "a" * 40
OTHER = "b" * 40
RECORD = handbacks.HandedBack(
    required=True, states=frozenset({(HEAD, "digest", "ruling")})
)


class TestCovers(unittest.TestCase):
    """What a record covers."""

    def test_a_pr_no_worker_holds_is_covered(self) -> None:
        """No worktree, no requirement."""
        covered = handbacks.covers(handbacks.NOT_REQUIRED, OTHER, "x", "y")
        same_state = handbacks.covers_state(handbacks.NOT_REQUIRED, OTHER, "x")
        assert_that((covered, same_state), equal_to((True, True)))

    def test_the_head_body_and_ruling_must_be_the_recorded_ones(self) -> None:
        """Each of the three."""
        asked = [
            (HEAD, "digest", "ruling"),
            (OTHER, "digest", "ruling"),
            (HEAD, "other", "ruling"),
            (HEAD, "digest", "other"),
        ]
        found = [handbacks.covers(RECORD, *each) for each in asked]
        assert_that(found, equal_to([True, False, False, False]))

    def test_a_review_names_the_head_abbreviated(self) -> None:
        """The head of a review may be a prefix, under any ruling."""
        asked = [(HEAD[:7], "digest"), (HEAD[:7], "other"), (OTHER[:7], "digest")]
        found = [handbacks.covers_state(RECORD, *each) for each in asked]
        assert_that(found, equal_to([True, False, False]))

    def test_a_ruling_is_applied_once_a_hand_back_names_it(self) -> None:
        """The ruling a hand-back saw."""
        found = [handbacks.applied(RECORD, "ruling"), handbacks.applied(RECORD, "x")]
        assert_that(found, equal_to([True, False]))


class TestRecord(unittest.TestCase):
    """The record in a worktree's git directory."""

    def test_a_record_is_a_line_of_three_words_and_an_older_line_is_the_head(
        self,
    ) -> None:
        """A new line holds the head, the body and the ruling; an older one the head."""
        record = repositories.directory() / handbackrecord.RECORD
        handbackrecord.record(record.parent, HEAD, "digest", "ruling")
        written = record.read_text(encoding="utf-8")
        record.write_text(f"{written}\n{OTHER}\n")
        older = (OTHER, handbacks.ANY, handbacks.ANY)
        both = {(HEAD, "digest", "ruling"), older}
        found = [written, handbackrecord.states(record.parent)]
        assert_that(found, equal_to([f"{HEAD} digest ruling\n", both]))

    def test_a_directory_with_no_record_has_no_states(self) -> None:
        """Nothing was handed back."""
        found = handbackrecord.states(repositories.directory())
        assert_that(found, equal_to(frozenset()))


class TestRead(unittest.TestCase):
    """The worktree of a branch."""

    def test_a_branch_with_no_worktree_is_not_required(self) -> None:
        """git cannot list a clone that is not there."""
        settings = fakes.settings(repositories.directory())
        ask = handedread.asker(_failing, settings)
        assert_that(ask("no-such-branch"), equal_to(handbacks.NOT_REQUIRED))

    def test_a_worktree_with_a_record_is_read(self) -> None:
        """A worktree of the branch: its record is the states."""
        made = repositories.build()
        clone = made.workspace / "project"
        path = repositories.add_worktree(clone, "work")
        git = pathlib.Path(handbackworld.git(path, "rev-parse", "--absolute-git-dir"))
        handbackrecord.record(git, HEAD, "digest", "ruling")
        settings = fakes.settings(made.workspace)
        ask = handedread.asker(_real, settings)
        found = ask("work")
        assert_that(found.required, equal_to(True))
        assert_that(found.states, equal_to(RECORD.states))
        assert_that(ask("other"), equal_to(handbacks.NOT_REQUIRED))


def _real(cmdargs: Sequence[str], /) -> running.Output:
    return fakes.run_for_real(cmdargs, None, None)


def _failing(cmdargs: Sequence[str], /) -> running.Output:
    raise OSError("no git")
