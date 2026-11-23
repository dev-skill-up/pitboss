"""A hand-back is required of any PR a worker pushed, whatever worktree exists."""

import pathlib
import unittest

from hamcrest import assert_that, equal_to

from .. import handbackrecord, handbacks, handedread
from . import handbackworld, repositories, world
from .handbackrun import hand_back, no_jobs
from .handbackworld import ready
from .test_handbacks import HEAD, RECORD, asked_of

BRANCH = "w1113/numbered"
OWED = handbacks.HandedBack(required=True, states=frozenset())


def _common(clone: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(handbackworld.git(clone, "rev-parse", "--absolute-git-dir"))


class TestDurable(unittest.TestCase):
    """A removed worktree takes no record, and no worktree frees no PR."""

    def test_a_branch_with_no_worktree_and_no_record_is_required_not_free(self) -> None:
        """quire#1125: its worktree was gone, and its rounds were all counted."""
        found = asked_of(repositories.build().workspace, "no-worktree")
        assert_that(found, equal_to(OWED))

    def test_a_record_survives_the_removal_of_its_worktree(self) -> None:
        """The record kept beside the clone is read after `git worktree remove`."""
        here = world.make_world()
        branch = handbackworld.git(here.worktree, "branch", "--show-current")
        common = _common(here.clone)
        handbackrecord.record(
            handbackrecord.kept(common, branch), HEAD, "digest", "ruling"
        )
        handbackworld.git(
            here.clone, "worktree", "remove", "--force", str(here.worktree)
        )
        left = asked_of(here.workspace, branch)
        assert_that((left.required, left.states), equal_to((True, RECORD.states)))

    def test_the_accepted_hand_back_is_kept_for_its_branch(self) -> None:
        """`hand-back-check` writes the record that outlives the worktree."""
        here = ready(world.make_world())
        done = hand_back(here, no_jobs(), "--pr", "7")
        branch = handbackworld.git(here.clone, "branch", "--show-current")
        kept = handbackrecord.kept(_common(here.clone), branch)
        pushed = handbackworld.git(here.clone, "rev-parse", "HEAD")
        own = [each for each in handbackrecord.states(kept) if each[1] != handbacks.ANY]
        assert_that((done.code, {each[0] for each in own}), equal_to((0, {pushed})))

    def test_only_a_relock_pr_is_freed_of_a_hand_back(self) -> None:
        """The branch's own answer is used for any other PR."""

        def ask(branch: str) -> handbacks.HandedBack:
            return OWED

        found = [
            handedread.held(ask, "relock/2026-11-23", "relock/"),
            handedread.held(ask, BRANCH, "relock/"),
        ]
        assert_that(found, equal_to([handbacks.NOT_REQUIRED, OWED]))

    def test_a_branch_name_is_one_directory(self) -> None:
        """A slash in the branch makes no nested directory."""
        kept = handbackrecord.kept(pathlib.Path("/c"), BRANCH)
        assert_that(kept.parent, equal_to(pathlib.Path("/c") / handbackrecord.KEPT))
