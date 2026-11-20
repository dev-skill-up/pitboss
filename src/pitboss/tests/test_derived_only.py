"""A head that adds only a rebuilt skill zip needs no new review (pitboss#323)."""

import json
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import mergesonly, shapes
from . import decisionline, quietworld, world
from .suggestions import kind_of_third
from .test_commands import sweep
from .test_flow_sweep import APPROVED, OLDER, graded, world_with

ZIP = "skill-zips/sweep.zip"
SOURCE = "src/pitboss/pulls.py"
RENAMED: Mapping[str, str] = {"filename": SOURCE, "previous_filename": ZIP}


def approved_older(files: Sequence[Mapping[str, str]]) -> world.World:
    """A world where PR 3 was approved at an older head.

    Args:
        files: the files the one commit since that head changes.

    Returns:
        The world.
    """
    here = world_with([graded("approved", APPROVED, 1, OLDER)])
    here.bodies.update({f"{world.PROJECT}/commits/2": {"files": files}})
    return quietworld.calm(here)


def third_line(files: Sequence[Mapping[str, str]]) -> str:
    """PR 3's state line in the sweep, approved at an older head.

    Args:
        files: the files the one commit since that head changes.

    Returns:
        The line.
    """
    return decisionline.state(sweep(approved_older(files)).out, "owner/project#3")


def named(*names: str) -> Sequence[Mapping[str, str]]:
    """Files as the API lists them.

    Args:
        *names: the paths.

    Returns:
        The files.
    """
    return [{"filename": name} for name in names]


class TestSweepLines(unittest.TestCase):
    """The review of a PR approved before a commit that changes files."""

    def test_only_the_zip_is_approved_before_merges(self) -> None:
        """Only skill-zips/ differs: approved, and the review is of the resolution."""
        assert_that(
            third_line(named(ZIP)), contains_string("review=approved-before-merges")
        )
        kind = kind_of_third(approved_older(named(ZIP)))
        assert_that(kind, equal_to("review the merge resolution only"))

    def test_the_zip_and_another_file_is_reviewed_as_before(self) -> None:
        """A mixed diff stays an older head; so do the nearest names."""
        mixed = [named(ZIP, SOURCE), named("skill-zips.txt"), [RENAMED]]
        for files in mixed:
            assert_that(third_line(files), contains_string("review=older-head"))
            kind = kind_of_third(approved_older(files))
            assert_that(kind, equal_to("review the Execution"))


class TestParts(unittest.TestCase):
    """The commit's files and the rule on them."""

    def test_file_names_read_both_paths_of_a_rename(self) -> None:
        """The old path of a renamed file is a path the commit changes."""
        text = json.dumps({"files": [{"filename": "b", "previous_filename": "a"}]})
        assert_that(mergesonly.file_names(text), equal_to(["b", "a"]))

    def test_a_commit_with_no_files_is_not_derived_only(self) -> None:
        """Nothing listed proves nothing."""
        found = [mergesonly.derived_only([]), mergesonly.derived_only([ZIP])]
        assert_that(found, equal_to([False, True]))

    def test_a_head_missing_a_reviewed_commit_is_not_carried(self) -> None:
        """A head that lacks a commit of the reviewed head is a rewrite."""
        kept, gone = (shapes.Commit(sha=each, parents=1) for each in "12")
        assert_that(mergesonly.added([kept], [kept, gone]), equal_to(None))
